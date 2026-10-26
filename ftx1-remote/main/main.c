/*
 * ftx1-remote: FH-2 相当のリモコン (ESP32-S3 が USB ホストとして FTX-1 の CAT-1 を操作)
 *
 * FH-2 (抵抗ラダー式キーパッド) の押下を ADC で判別し、FTX-1 へ CAT コマンドを送る。
 *   CW バンク : KEY 1-5 -> KY11; ～ KY15;  (CW MESSAGE メモリー再生)
 *   SSB バンク: KEY 1-5 -> PB01; ～ PB05;  (ボイスメモリー再生)
 *   KEY 6 (MEM): バンク切替 (CW <-> SSB)
 *   KEY 12 (DEC): 再生停止 (KY10; と PB00;)
 *
 * 根拠: FTX-1 CAT Operation Reference Manual 2512-D (KY / PB / USB 接続の章)
 *
 * VERSION = 1.0.0
 *
 * 変更履歴:
 *   1.0.0  初版。FH-2 抵抗ラダー(4.7kΩ プルアップ, 3.3V)を ADC で判別、
 *          CP210x (CP2105 想定) の CAT-1 へ KY/PB を送出。
 *          ※実機・コンパイル未検証。README.md の検証手順を参照。
 */

#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "driver/gpio.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "usb/usb_host.h"
#include "usb/cdc_acm_host.h"
#include "usb/vcp_cp210x.h"

#define VERSION "1.0.0"
static const char *TAG = "ftx1-remote";

/* ---- 設定値 (配線に合わせて変更) ---- */
#define KEY_ADC_UNIT      ADC_UNIT_1
#define KEY_ADC_CHANNEL   ADC_CHANNEL_3     /* ESP32-S3: ADC1_CH3 = GPIO4 */
#define PULLUP_OHM        4700              /* GPIO4 - 3V3 間のプルアップ */
#define VREF_MV           3300
#define NONE_MV           3000              /* これ以上は「無押下」 */
#define SHORT_MV          250               /* これ未満は短絡扱い(無視) */

#define LED_CW_GPIO       GPIO_NUM_6
#define LED_SSB_GPIO      GPIO_NUM_7

#define CAT_BAUD          38400             /* CAT-1 (Enhanced COM) 既定 */
#define CAT_INTERFACE_IDX 0                 /* CP2105: 0=Enhanced(CAT-1) と想定。要実機確認 */
#ifndef CP210X_PID_AUTO
#define CP210X_PID_AUTO   0
#endif

#define KEY_MEM_INDEX     5                 /* 表の KEY 6  (4120Ω) */
#define KEY_STOP_INDEX    11                /* 表の KEY 12 (25550Ω) */
#define DEBUG_PRINT_MV    0                 /* 1 で押下時に mV を表示 (しきい値確認用) */

/* FH-2 の各キーの抵抗値 (FH-2 取扱説明書のリモート回路表 KEY1-12) */
static const int KEY_OHM[12] = {866, 1330, 1820, 2490, 3240, 4120,
                                5360, 6810, 8870, 12000, 16900, 25550};

/* ---- 状態 ---- */
typedef enum { BANK_CW = 0, BANK_SSB = 1 } bank_t;
static bank_t g_bank = BANK_CW;

static cdc_acm_dev_hdl_t volatile g_cat = NULL;
static int g_upper_mv[12];                  /* 各キーの判定上限 (中点) */

static adc_oneshot_unit_handle_t g_adc;
static adc_cali_handle_t g_cali;

/* ---- LED ---- */
static void led_update(void)
{
    gpio_set_level(LED_CW_GPIO, g_bank == BANK_CW);
    gpio_set_level(LED_SSB_GPIO, g_bank == BANK_SSB);
}

static void led_init(void)
{
    gpio_config_t io = {
        .pin_bit_mask = (1ULL << LED_CW_GPIO) | (1ULL << LED_SSB_GPIO),
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&io);
    led_update();
}

/* ---- CAT 送信 ---- */
static void cat_send(const char *cmd)
{
    cdc_acm_dev_hdl_t h = g_cat;
    if (h == NULL) {
        ESP_LOGW(TAG, "FTX-1 未接続のため送信しない: %s", cmd);
        return;
    }
    esp_err_t err = cdc_acm_host_data_tx_blocking(h, (const uint8_t *)cmd, strlen(cmd), 1000);
    ESP_LOGI(TAG, "TX %s -> %s", cmd, esp_err_to_name(err));
}

static void do_play(int ch)             /* ch: 1-5 */
{
    char buf[8];
    if (g_bank == BANK_CW) {
        snprintf(buf, sizeof(buf), "KY1%d;", ch);   /* CW MESSAGE メモリー ch 再生 */
    } else {
        snprintf(buf, sizeof(buf), "PB0%d;", ch);   /* ボイスメモリー CH ch 再生 */
    }
    cat_send(buf);
}

static void do_stop(void)
{
    cat_send("KY10;");
    vTaskDelay(pdMS_TO_TICKS(30));
    cat_send("PB00;");
}

static void on_key(int idx)             /* idx: 0-11 (表の KEY1-12) */
{
    if (idx >= 0 && idx <= 4) {
        do_play(idx + 1);
    } else if (idx == KEY_MEM_INDEX) {
        g_bank = (g_bank == BANK_CW) ? BANK_SSB : BANK_CW;
        led_update();
        ESP_LOGI(TAG, "bank = %s", g_bank == BANK_CW ? "CW" : "SSB");
    } else if (idx == KEY_STOP_INDEX) {
        do_stop();
    }
    /* それ以外のキーは未使用 */
}

/* ---- FH-2 キー判別 ---- */
static void key_thresholds_init(void)
{
    int nominal[12];
    for (int i = 0; i < 12; i++) {
        nominal[i] = (int)((long)VREF_MV * KEY_OHM[i] / (PULLUP_OHM + KEY_OHM[i]));
    }
    for (int i = 0; i < 11; i++) {
        g_upper_mv[i] = (nominal[i] + nominal[i + 1]) / 2;
    }
    g_upper_mv[11] = NONE_MV;
}

static void adc_init(void)
{
    adc_oneshot_unit_init_cfg_t ucfg = {.unit_id = KEY_ADC_UNIT};
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&ucfg, &g_adc));
    adc_oneshot_chan_cfg_t ccfg = {.atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT};
    ESP_ERROR_CHECK(adc_oneshot_config_channel(g_adc, KEY_ADC_CHANNEL, &ccfg));
    adc_cali_curve_fitting_config_t cal = {
        .unit_id = KEY_ADC_UNIT,
        .chan = KEY_ADC_CHANNEL,
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    ESP_ERROR_CHECK(adc_cali_create_scheme_curve_fitting(&cal, &g_cali));
}

static int read_mv(void)
{
    int sum = 0;
    for (int i = 0; i < 16; i++) {
        int raw = 0;
        adc_oneshot_read(g_adc, KEY_ADC_CHANNEL, &raw);
        sum += raw;
    }
    int mv = 0;
    adc_cali_raw_to_voltage(g_cali, sum / 16, &mv);
    return mv;
}

/* 戻り値: 0-11 = キー, -1 = 無押下/無効 */
static int classify(int mv)
{
    if (mv >= NONE_MV || mv < SHORT_MV) {
        return -1;
    }
    for (int i = 0; i < 12; i++) {
        if (mv < g_upper_mv[i]) {
            return i;
        }
    }
    return -1;
}

static void key_task(void *arg)
{
    int stable = -1, cand = -1, count = 0;
    while (1) {
        int mv = read_mv();
        int k = classify(mv);
        if (k == cand) {
            if (count < 1000) count++;
        } else {
            cand = k;
            count = 1;
        }
        if (count == 3 && cand != stable) {     /* 3 回(約 30ms)連続一致で確定 */
            stable = cand;
            if (stable >= 0) {                  /* 押下エッジのみ処理 */
#if DEBUG_PRINT_MV
                ESP_LOGI(TAG, "KEY%d mv=%d", stable + 1, mv);
#endif
                on_key(stable);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

/* ---- USB ホスト (FTX-1 CAT-1) ---- */
static void usb_lib_task(void *arg)
{
    while (1) {
        uint32_t flags;
        usb_host_lib_handle_events(portMAX_DELAY, &flags);
        if (flags & USB_HOST_LIB_EVENT_FLAGS_NO_CLIENTS) {
            usb_host_device_free_all();
        }
    }
}

static bool rx_cb(const uint8_t *data, size_t len, void *user_arg)
{
    ESP_LOGI(TAG, "RX %.*s", (int)len, (const char *)data);   /* 応答 ("?;" など) をログ */
    return true;
}

static void dev_event_cb(const cdc_acm_host_dev_event_data_t *event, void *user_ctx)
{
    if (event->type == CDC_ACM_HOST_DEVICE_DISCONNECTED) {
        ESP_LOGW(TAG, "FTX-1 切断");
        cdc_acm_host_close(event->data.cdc_hdl);
        g_cat = NULL;
    }
}

static void cat_connect_task(void *arg)
{
    const cdc_acm_host_device_config_t cfg = {
        .connection_timeout_ms = 1000,
        .out_buffer_size = 64,
        .in_buffer_size = 64,
        .event_cb = dev_event_cb,
        .data_cb = rx_cb,
        .user_arg = NULL,
    };
    while (1) {
        if (g_cat == NULL) {
            cdc_acm_dev_hdl_t h = NULL;
            esp_err_t err = cp210x_vcp_open(CP210X_PID_AUTO, CAT_INTERFACE_IDX, &cfg, &h);
            if (err == ESP_OK) {
                cdc_acm_line_coding_t lc = {
                    .dwDTERate = CAT_BAUD,
                    .bCharFormat = 0,           /* 1 stop bit */
                    .bParityType = 0,
                    .bDataBits = 8,
                };
                cdc_acm_host_line_coding_set(h, &lc);
                cdc_acm_host_set_control_line_state(h, false, false);   /* DTR/RTS は触らない */
                g_cat = h;
                ESP_LOGI(TAG, "FTX-1 接続 (CAT-1, %d bps)", CAT_BAUD);
                cat_send("FA;");                /* 疎通確認: 周波数読み出し。応答が RX に出る */
            }
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "ftx1-remote %s", VERSION);
    led_init();
    key_thresholds_init();
    adc_init();

    usb_host_config_t host_cfg = {.skip_phy_setup = false, .intr_flags = ESP_INTR_FLAG_LEVEL1};
    ESP_ERROR_CHECK(usb_host_install(&host_cfg));
    xTaskCreate(usb_lib_task, "usb_lib", 4096, NULL, 10, NULL);
    ESP_ERROR_CHECK(cdc_acm_host_install(NULL));

    xTaskCreate(cat_connect_task, "cat_conn", 4096, NULL, 5, NULL);
    xTaskCreate(key_task, "key", 4096, NULL, 5, NULL);
}

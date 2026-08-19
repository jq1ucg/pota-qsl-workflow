#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FD/6DN ADIF QSO抽出・タグ付与スクリプト
ADIF から FD期間と6DN期間のQSOレコードを抽出し、
各々に異なるSTATION_CALLSIGN/MY_STATE/MY_CNTY/JCCJCGAJAタグを付与する
"""

import re
import sys

# 期間設定
FD_START = "202608010000"   # 2026/08/01 00:00
FD_END = "202608020600"     # 2026/08/02 06:00
SIX_START = "202607040000"  # 2026/07/04 00:00
SIX_END = "202607050600"    # 2026/07/05 06:00

def extract_datetime(line):
    """QSOレコードから日時を抽出"""
    # 日付抽出
    date_match = re.search(r'<qso_date:\d+>(\d{8})', line)
    date = date_match.group(1) if date_match else ""
    
    # 時刻抽出
    time_match = re.search(r'<time_on:\d+>(\d{4})', line)
    time = time_match.group(1)[:4] if time_match else "0000"
    
    return date + time

def add_fd_tags(line):
    """FD側タグを付与"""
    line = line.rstrip('\r\n')
    if not line.endswith('<eor>'):
        return line + '\n'
    
    line = line[:-5]  # <eor> を削除
    
    tags = [
        '<station_callsign:8>JL1ICY/1',
        '<my_state:2>10',
        '<my_cnty:8>10,100123',
        '<jccjcgaja:9>JCC100123'
    ]
    
    return line + ' ' + ' '.join(tags) + ' <eor>\n'

def add_six_tags(line):
    """6DN側タグを付与"""
    line = line.rstrip('\r\n')
    if not line.endswith('<eor>'):
        return line + '\n'
    
    line = line[:-5]  # <eor> を削除
    
    tags = [
        '<station_callsign:8>JL1ICY/1',
        '<my_state:2>12',
        '<my_cnty:7>12,1224',
        '<jccjcgaja:7>JCC1224'
    ]
    
    return line + ' ' + ' '.join(tags) + ' <eor>\n'

def main():
    if len(sys.argv) < 2:
        print("使用方法: python3 extract_fd_6dn.py <input.adif>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    fd_lines = []
    six_lines = []
    
    # 入力ファイルを読み込み
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip('\n\r')
                
                # 日時抽出
                datetime = extract_datetime(line)
                
                # FD/6DN判定
                is_fd = FD_START <= datetime <= FD_END
                is_six = SIX_START <= datetime <= SIX_END
                
                if is_fd:
                    fd_lines.append(line)
                
                if is_six:
                    six_lines.append(line)
    except FileNotFoundError:
        print(f"エラー: ファイルが見つかりません: {input_file}")
        sys.exit(1)
    
    # FD側ファイル出力
    fd_out = "filterd-FD.adif"
    with open(fd_out, "w", encoding="utf-8") as f:
        f.write("Generated ADIF File\n<eor>\n")
        for line in fd_lines:
            f.write(add_fd_tags(line))
    
    # 6DN側ファイル出力
    six_out = "filterd-6DN.adif"
    with open(six_out, "w", encoding="utf-8") as f:
        f.write("Generated ADIF File\n<eor>\n")
        for line in six_lines:
            f.write(add_six_tags(line))
    
    # 結果表示
    print(f"✓ {fd_out}: {len(fd_lines)} QSO (10,100123,JCC100123)")
    print(f"✓ {six_out}: {len(six_lines)} QSO (12,1224,JCC1224)")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
CLI kullanımı:
  python run.py input.txt              → sonucu ekrana yazar
  python run.py input.txt output.sql   → dosyaya kaydeder
"""

import sys
from sql_converter import convert_sql, format_output


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python run.py <input.txt> [output.sql]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        with open(input_file, encoding='utf-8-sig') as f:
            sql_text = f.read()
    except UnicodeDecodeError:
        with open(input_file, encoding='latin-1') as f:
            sql_text = f.read()

    result = convert_sql(sql_text)
    output = format_output(result)

    s = result['stats']
    print(f"\n{'='*55}")
    print(f"  INSERT: {s['insert']}  |  UPDATE: {s['update']}  |  DELETE: {s['delete']}  |  Atlandı: {s['skipped']}")
    if result['errors']:
        print(f"\n  UYARILAR ({len(result['errors'])}):")
        for err in result['errors']:
            print(f"    - {err}")
    print('='*55)

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"\n✓ Sonuç kaydedildi: {output_file}\n")
    else:
        print()
        print(output)


if __name__ == '__main__':
    main()

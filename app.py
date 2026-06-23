from flask import Flask, render_template, request, jsonify, send_file
import tempfile
from datetime import datetime
from sql_converter import convert_sql, format_output

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/convert', methods=['POST'])
def convert():
    sql_text = ''

    if 'file' in request.files and request.files['file'].filename:
        raw = request.files['file'].read()
        try:
            sql_text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            sql_text = raw.decode('latin-1', errors='replace')
    elif request.form.get('sql_text'):
        sql_text = request.form.get('sql_text')
    else:
        return jsonify({'error': 'SQL metni veya dosya gereklidir'}), 400

    result = convert_sql(sql_text) # type: ignore
    output = format_output(result)

    return jsonify({
        'output': output,
        'stats': result['stats'],
        'errors': result['errors'],
        'statements': result['statements'],
        'table_summary': result['table_summary'],
    })


@app.route('/test_db', methods=['POST'])
def test_db():
    try:
        import oracledb
    except ImportError:
        return jsonify({'error': 'oracledb kütüphanesi eksik. pip install oracledb çalıştırın.'}), 500

    data     = request.get_json(force=True)
    host     = (data.get('host') or '').strip()
    port     = int(data.get('port') or 1521)
    service  = (data.get('service') or '').strip()
    user     = (data.get('user') or '').strip()
    password = (data.get('password') or '').strip()
    stmts    = data.get('statements', [])

    if not (host and service and user):
        return jsonify({'error': 'Host, servis adı ve kullanıcı adı zorunludur.'}), 400

    try:
        conn = oracledb.connect(user=user, password=password,
                                dsn=f'{host}:{port}/{service}')
    except Exception as e:
        return jsonify({'error': f'Bağlantı hatası: {e}'}), 400

    results = []
    try:
        cur = conn.cursor()
        for stmt in stmts:
            idx = stmt['index']
            sql = (stmt.get('select') or '').strip()
            if not sql:
                results.append({'index': idx, 'status': 'SKIP', 'result': ''})
                continue
            try:
                cur.execute(sql)
                row = cur.fetchone()
                sonuc = str(row[1]) if row and len(row) > 1 else (str(row[0]) if row else '')
                results.append({'index': idx, 'status': 'OK', 'result': sonuc})
            except Exception as e:
                results.append({'index': idx, 'status': 'FAIL', 'result': str(e)})
        cur.close()
    finally:
        conn.close()

    return jsonify({'results': results})


@app.route('/download', methods=['POST'])
def download():
    output = request.form.get('output', '')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    tmp = tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.sql',
        prefix=f'dogrulama_{ts}_',
        delete=False,
        encoding='utf-8',
    )
    tmp.write(output)
    tmp.flush()
    tmp_path = tmp.name
    tmp.close()

    return send_file(
        tmp_path,
        as_attachment=True,
        download_name=f'dogrulama_{ts}.sql',
        mimetype='text/plain',
    )


if __name__ == '__main__':
    print("SQL Doğrulama & Risk Analizi uygulaması başlatılıyor...")
    print("Tarayıcıda açın: http://127.0.0.1:5001")
    app.run(debug=True, port=5001)

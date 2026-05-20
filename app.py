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

    result = convert_sql(sql_text)
    output = format_output(result)

    return jsonify({
        'output': output,
        'stats': result['stats'],
        'errors': result['errors'],
        'statements': result['statements'],
        'table_summary': result['table_summary'],
    })


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

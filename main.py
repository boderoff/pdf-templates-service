#!/usr/bin/env python3.14

"""
PDF генератор на Python 3.14 с t-strings
Запуск: python main.py
"""

import subprocess
import sys
import importlib

# автоустановка зависимостей
deps = [('flask', 'flask'), ('flask_cors', 'flask-cors'), ('xhtml2pdf', 'xhtml2pdf'), ('reportlab', 'reportlab')]
for import_name, pip_name in deps:
    try:
        importlib.import_module(import_name)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pip_name])

import sqlite3
import io
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from flask import Flask, request, jsonify, render_template_string, send_file
from flask_cors import CORS
from xhtml2pdf import pisa
from xhtml2pdf import default as pisa_default
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)
CORS(app)
DB_PATH = "templates.db"
BASE_DIR = Path(__file__).parent
FONTS_DIR = BASE_DIR / "fonts"

# подключаем шрифт для русского языка в PDF
font_path = FONTS_DIR / "times.ttf"
if font_path.exists():
    try:
        pdfmetrics.registerFont(TTFont("TimesNewRoman", str(font_path)))
        pisa_default.DEFAULT_FONT["timesnewroman"] = "TimesNewRoman"
        pisa_default.DEFAULT_FONT["times new roman"] = "TimesNewRoman"
        print("✓ шрифт TimesNewRoman загружен")
    except Exception as e:
        print(f"ошибка шрифта: {e}")
else:
    print("шрифт не найден, создайте папку fonts и положите times.ttf")

# создаём таблицу в sqlite
conn = sqlite3.connect(DB_PATH)
conn.execute('''
             CREATE TABLE IF NOT EXISTS templates
             (
                 id
                 INTEGER
                 PRIMARY
                 KEY
                 AUTOINCREMENT,
                 name
                 TEXT
                 NOT
                 NULL,
                 content
                 TEXT
                 NOT
                 NULL,
                 created_at
                 TIMESTAMP
                 DEFAULT
                 CURRENT_TIMESTAMP,
                 updated_at
                 TIMESTAMP
                 DEFAULT
                 CURRENT_TIMESTAMP
             )
             ''')
conn.commit()
conn.close()


# подстановка переменных {value} из JSON
def substitute(content: str, data: Dict[str, Any]) -> str:
    def get_value(obj, path):
        parts = re.split(r'\.|\[|\]', path)
        parts = [p for p in parts if p]
        cur = obj
        for p in parts:
            if p.isdigit():
                cur = cur[int(p)]
            elif isinstance(cur, dict):
                cur = cur.get(p, f'{{{{{path}}}}}')
            elif isinstance(cur, list):
                try:
                    cur = cur[int(p)]
                except:
                    return f'{{{{{path}}}}}'
            else:
                return f'{{{{{path}}}}}'
        return str(cur) if cur is not None else ''

    return re.sub(r'\{([^}]+)\}', lambda m: get_value(data, m.group(1)), content)


# конвертация HTML в PDF
def to_pdf(html: str) -> bytes:
    full = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: TimesNewRoman, 'Times New Roman', Times, serif;
            margin: 20px;
            font-size: 14px;
            line-height: 1.5;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 10px 0;
        }}
        th, td {{
            border: 1px solid #999;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f0f0f0;
        }}
        h1, h2, h3 {{
            margin-bottom: 10px;
        }}
        ul, ol {{
            margin: 10px 0;
            padding-left: 25px;
        }}
        hr {{
            margin: 20px 0;
            border: none;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
{html}
</body>
</html>'''
    buf = io.BytesIO()
    pisa.CreatePDF(io.StringIO(full), dest=buf, encoding='utf-8')
    buf.seek(0)
    return buf.getvalue()


# весь HTML интерфейс с Quill редактором
HTML_UI = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>PDF Генератор</title>
    <link href="https://cdn.quilljs.com/1.3.6/quill.snow.css" rel="stylesheet">
    <script src="https://cdn.quilljs.com/1.3.6/quill.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Times New Roman', Times, serif; background: #f0f2f5; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: white; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        h1 { font-size: 24px; color: #333; }
        .controls { display: flex; gap: 10px; margin: 15px 0 0; flex-wrap: wrap; }
        button, select, input { padding: 8px 15px; border: 1px solid #ddd; border-radius: 5px; background: white; cursor: pointer; font-family: 'Times New Roman', Times, serif; }
        button:hover { background: #007bff; color: white; border-color: #007bff; }
        .btn-primary { background: #007bff; color: white; }
        .btn-danger:hover { background: #dc3545; border-color: #dc3545; }
        .editor-container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .panel { background: white; border-radius: 8px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .panel-title { font-weight: bold; margin-bottom: 10px; }
        #editor { height: 400px; }
        .preview-frame { width: 100%; height: 500px; border: 1px solid #ddd; border-radius: 5px; }
        .fields-panel { margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 5px; }
        .field-row { display: flex; gap: 10px; margin-bottom: 8px; align-items: center; }
        .field-row input { flex: 1; padding: 6px 10px; }
        .field-row input:first-child { font-family: monospace; background: #e9ecef; }
        .field-row button { padding: 6px 12px; background: #dc3545; color: white; border: none; cursor: pointer; }
        .field-row button:hover { background: #c82333; }
        .add-field { margin-top: 10px; padding: 6px 12px; background: #28a745; color: white; border: none; cursor: pointer; }
        .add-field:hover { background: #218838; }
        textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-family: monospace; margin-top: 10px; }
        .status {
    margin-top: 20px;
    padding: 12px 20px;
    border-radius: 8px;
    display: none;
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 9999;
    min-width: 250px;
    max-width: 400px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    font-size: 14px;
}
.status.success {
    background: #d4edda;
    color: #155724;
    display: block;
    border-left: 4px solid #28a745;
}
.status.error {
    background: #f8d7da;
    color: #721c24;
    display: block;
    border-left: 4px solid #dc3545;
}
        .success { background: #d4edda; color: #155724; display: block; }
        .error { background: #f8d7da; color: #721c24; display: block; }
        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); }
        .modal-content { background: white; margin: 15% auto; padding: 20px; width: 400px; border-radius: 10px; text-align: center; }
        .modal-content button { margin: 10px; padding: 8px 20px; }
        @media (max-width: 768px) { .editor-container { grid-template-columns: 1fr; } }
        .ql-editor { font-family: 'Times New Roman', Times, serif; }
        .mode-switch { display: flex; gap: 10px; margin-bottom: 10px; }
        .mode-btn { flex: 1; text-align: center; padding: 8px; background: #e9ecef; border: none; cursor: pointer; border-radius: 5px; }
        .mode-btn.active { background: #007bff; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PDF Генератор</h1>
            <div class="controls">
                <input type="text" id="templateName" placeholder="Название шаблона" style="flex:1">
                <select id="templateSelect" style="flex:2">
                    <option value="">-- Выберите шаблон --</option>
                </select>
                <button onclick="saveTemplate()" class="btn-primary">Сохранить</button>
                <button onclick="deleteTemplate()" class="btn-danger">Удалить</button>
                <button onclick="renderPDF()">Скачать PDF</button>
                <button onclick="previewHTML()">Предпросмотр</button>
            </div>
        </div>
        <div class="editor-container">
            <div class="panel">
                <div class="panel-title">HTML шаблон (используйте {переменная})</div>
                <div id="editor"></div>
                <div class="fields-panel">
                    <div class="mode-switch">
                        <button class="mode-btn active" onclick="setMode('fields')">Режим полей</button>
                        <button class="mode-btn" onclick="setMode('json')"> Режим JSON</button>
                    </div>
                    <div id="fieldsMode">
                        <div id="fieldsList"></div>
                        <button class="add-field" onclick="addField()">+ Добавить поле</button>
                    </div>
                    <div id="jsonMode" style="display:none">
                        <textarea id="jsonData" rows="8">{
  "title": "Образец документа",
  "content": "Это пример содержимого",
  "date": "2026-05-28",
  "author": "Иван Петров",
  "price": "99.99",
  "quantity": "5",
  "user": {"name": "Анна Смирнова"},
  "items": ["Товар 1", "Товар 2"]
}</textarea>
                    </div>
                </div>
            </div>
            <div class="panel">
                <div class="panel-title">Предпросмотр</div>
                <iframe id="previewFrame" class="preview-frame"></iframe>
            </div>
        </div>
        <div id="status" class="status"></div>
    </div>

    <div id="confirmModal" class="modal">
        <div class="modal-content">
            <h3>Подтверждение</h3>
            <p>Шаблон "<span id="dupName"></span>" уже существует.</p>
            <p>Обновить?</p>
            <button onclick="confirmUpdate()" class="btn-primary">Да, обновить</button>
            <button onclick="closeModal()">Отмена</button>
        </div>
    </div>

    <script>
        // переменные
        let quill = new Quill('#editor', { theme: 'snow', placeholder: 'Введите шаблон...' });
        let currentId = null;
        let currentMode = 'fields';
        let pendingName = null;
        let pendingContent = null;

        // переключение между режимами
        function setMode(mode) {
            currentMode = mode;
            document.querySelectorAll('.mode-btn').forEach(btn => btn.classList.remove('active'));
            if (mode === 'fields') {
                document.querySelector('.mode-btn:first-child').classList.add('active');
                document.getElementById('fieldsMode').style.display = 'block';
                document.getElementById('jsonMode').style.display = 'none';
                updateJsonFromFields();
            } else {
                document.querySelector('.mode-btn:last-child').classList.add('active');
                document.getElementById('fieldsMode').style.display = 'none';
                document.getElementById('jsonMode').style.display = 'block';
                updateFieldsFromJson();
            }
        }

        // добавить поле ввода
        function addField(key = '', value = '') {
            let div = document.createElement('div');
            div.className = 'field-row';
            div.innerHTML = `
                <input type="text" placeholder="Название поля" value="${escapeHtml(key)}" onchange="updateJsonFromFields()">
                <input type="text" placeholder="Значение" value="${escapeHtml(value)}" onchange="updateJsonFromFields()">
                <button onclick="this.parentElement.remove(); updateJsonFromFields()">✕</button>
            `;
            document.getElementById('fieldsList').appendChild(div);
            updateJsonFromFields();
        }

        function escapeHtml(str) {
            return str.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            });
        }

        // синхронизация полей -> JSON
        function updateJsonFromFields() {
            if (currentMode !== 'fields') return;
            let fields = {};
            document.querySelectorAll('#fieldsList .field-row').forEach(row => {
                let inputs = row.querySelectorAll('input');
                let key = inputs[0].value.trim();
                let value = inputs[1].value;
                if (key) fields[key] = value;
            });
            document.getElementById('jsonData').value = JSON.stringify(fields, null, 2);
        }

        // синхронизация JSON -> поля
        function updateFieldsFromJson() {
            if (currentMode !== 'json') return;
            try {
                let data = JSON.parse(document.getElementById('jsonData').value);
                let container = document.getElementById('fieldsList');
                container.innerHTML = '';
                for (let [key, value] of Object.entries(data)) {
                    addField(key, String(value));
                }
                if (Object.keys(data).length === 0) addField('', '');
            } catch(e) {
                console.log('ошибка парсинга JSON');
            }
        }

        // получить текущие данные
        function getCurrentData() {
            if (currentMode === 'fields') updateJsonFromFields();
            try {
                return JSON.parse(document.getElementById('jsonData').value);
            } catch(e) {
                return {};
            }
        }

        // загрузить список шаблонов
        async function loadTemplates() {
            let r = await fetch('/templates');
            let templates = await r.json();
            let select = document.getElementById('templateSelect');
            let savedValue = select.value;
            select.innerHTML = '<option value="">-- Выберите шаблон --</option>';
            templates.forEach(t => {
                let opt = document.createElement('option');
                opt.value = t.id;
                opt.textContent = `${t.name} (${new Date(t.updated_at).toLocaleDateString()})`;
                select.appendChild(opt);
            });
            if (savedValue) select.value = savedValue;
        }

        // показать модальное окно
        function showModal(name, content) {
            document.getElementById('dupName').textContent = name;
            pendingName = name;
            pendingContent = content;
            document.getElementById('confirmModal').style.display = 'block';
        }

        function closeModal() {
            document.getElementById('confirmModal').style.display = 'none';
            pendingName = null;
            pendingContent = null;
        }

        // подтвердить обновление
        async function confirmUpdate() {
            closeModal();
            if (pendingName && pendingContent) {
                let r = await fetch('/templates/update_by_name', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: pendingName, content: pendingContent})
                });
                if (r.ok) {
                    let d = await r.json();
                    currentId = d.id;
                    document.getElementById('templateName').value = d.name;
                    showStatus('Сохранено', 'success');
                    loadTemplates();
                } else {
                    showStatus('Ошибка', 'error');
                }
                pendingName = null;
                pendingContent = null;
            }
        }

        // сохранить шаблон
        async function saveTemplate() {
            let name = document.getElementById('templateName').value;
            if (!name) {
                showStatus('Введите название', 'error');
                return;
            }
            let content = quill.root.innerHTML;

            if (currentId) {
                let r = await fetch(`/templates/${currentId}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name, content})
                });
                if (r.ok) {
                    showStatus('Сохранено', 'success');
                    loadTemplates();
                } else if (r.status == 409) {
                    let err = await r.json();
                    if (err.exists) showModal(name, content);
                } else {
                    showStatus('Ошибка', 'error');
                }
                return;
            }

            let checkR = await fetch(`/templates/check_name/${encodeURIComponent(name)}`);
            let check = await checkR.json();
            if (check.exists) {
                showModal(name, content);
                return;
            }

            let r = await fetch('/templates', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name, content})
            });
            if (r.ok) {
                let d = await r.json();
                currentId = d.id;
                document.getElementById('templateName').value = d.name;
                showStatus('Сохранено', 'success');
                loadTemplates();
            } else {
                showStatus('Ошибка', 'error');
            }
        }

        // загрузить шаблон при выборе
        document.getElementById('templateSelect').onchange = async (e) => {
            let id = e.target.value;
            if (!id) return;
            let r = await fetch(`/templates/${id}`);
            if (r.ok) {
                let t = await r.json();
                document.getElementById('templateName').value = t.name;
                quill.root.innerHTML = t.content;
                currentId = t.id;
                showStatus('Загружено', 'success');
            }
        };

        // удалить шаблон
        async function deleteTemplate() {
            if (!currentId) {
                showStatus('Выберите шаблон', 'error');
                return;
            }
            if (!confirm('Удалить шаблон?')) return;
            let r = await fetch(`/templates/${currentId}`, { method: 'DELETE' });
            if (r.ok) {
                currentId = null;
                document.getElementById('templateName').value = '';
                quill.root.innerHTML = '';
                document.getElementById('templateSelect').value = '';
                showStatus('Удалено', 'success');
                loadTemplates();
            } else {
                showStatus('Ошибка', 'error');
            }
        }

        // скачать PDF
        async function renderPDF() {
            if (!currentId) {
                showStatus('Сначала сохраните шаблон', 'error');
                return;
            }
            try {
                let data = getCurrentData();
                let r = await fetch(`/render/${currentId}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                if (r.ok) {
                    let blob = await r.blob();
                    let url = URL.createObjectURL(blob);
                    let a = document.createElement('a');
                    a.href = url;
                    a.download = `документ_${Date.now()}.pdf`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    showStatus('PDF скачан', 'success');
                } else {
                    showStatus('Ошибка генерации', 'error');
                }
            } catch(e) {
                showStatus('Ошибка: ' + e.message, 'error');
            }
        }

        // показать предпросмотр
        async function previewHTML() {
            if (!currentId) {
                showStatus('Сначала сохраните шаблон', 'error');
                return;
            }
            try {
                let data = getCurrentData();
                let r = await fetch(`/preview/${currentId}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                if (r.ok) {
                    let html = await r.text();
                    document.getElementById('previewFrame').srcdoc = html;
                    showStatus('Предпросмотр обновлен', 'success');
                } else {
                    showStatus('Ошибка', 'error');
                }
            } catch(e) {
                showStatus('Ошибка', 'error');
            }
        }

        // показать сообщение
        function showStatus(msg, type) {
            let s = document.getElementById('status');
            s.textContent = msg;
            s.className = `status ${type}`;
            setTimeout(() => s.className = 'status', 3000);
        }

        // инициализация
        loadTemplates();
        addField('title', 'Образец документа');
        addField('author', 'Иван Петров');
        addField('date', '2026-05-28');
        addField('content', 'Пример содержимого');

        setTimeout(() => {
            if (!quill.root.innerHTML || quill.root.innerHTML === '<p><br></p>') {
                quill.root.innerHTML = `
                    <h1>{title}</h1>
                    <p><strong>Автор:</strong> {author}</p>
                    <p><strong>Дата:</strong> {date}</p>
                    <hr>
                    <p>{content}</p>
                `;
            }
        }, 500);
    </script>
</body>
</html>
'''


# ============================================================
# API ЭНДПОИНТЫ
# ============================================================

@app.route('/')
def index():
    """главная страница"""
    return render_template_string(HTML_UI)


@app.route('/templates', methods=['GET'])
def list_templates():
    """получить список всех шаблонов"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    templates = [dict(row) for row in conn.execute(
        'SELECT id, name, created_at, updated_at FROM templates ORDER BY updated_at DESC').fetchall()]
    conn.close()
    return jsonify(templates)


@app.route('/templates/check_name/<name>', methods=['GET'])
def check_template_name(name):
    """проверить, существует ли шаблон с таким именем"""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute('SELECT id FROM templates WHERE name = ?', (name,)).fetchone()
    conn.close()
    return jsonify({'exists': row is not None, 'id': row[0] if row else None})


@app.route('/templates/update_by_name', methods=['POST'])
def update_template_by_name():
    """обновить шаблон по имени (для случая когда имя уже есть)"""
    data = request.json
    name = data.get('name')
    content = data.get('content')
    if not name or not content:
        return jsonify({'error': 'нужны name и content'}), 400

    conn = sqlite3.connect(DB_PATH)
    row = conn.execute('SELECT id FROM templates WHERE name = ?', (name,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'шаблон не найден'}), 404

    tid = row[0]
    conn.execute('UPDATE templates SET name = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                 (name, content, tid))
    conn.commit()
    conn.close()
    return jsonify({'id': tid, 'name': name})


@app.route('/templates', methods=['POST'])
def create_template():
    """создать новый шаблон"""
    data = request.json
    if not data.get('name') or not data.get('content'):
        return jsonify({'error': 'нужны name и content'}), 400

    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute('INSERT INTO templates (name, content) VALUES (?, ?)', (data['name'], data['content']))
    conn.commit()
    tid = cur.lastrowid
    conn.close()
    return jsonify({'id': tid, 'name': data['name']}), 201


@app.route('/templates/<int:tid>', methods=['GET'])
def get_template(tid):
    """получить шаблон по id"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    t = conn.execute('SELECT * FROM templates WHERE id = ?', (tid,)).fetchone()
    conn.close()
    if not t:
        return jsonify({'error': 'шаблон не найден'}), 404
    return jsonify(dict(t))


@app.route('/templates/<int:tid>', methods=['PUT'])
def update_template(tid):
    """обновить шаблон"""
    data = request.json
    if not data.get('name') or not data.get('content'):
        return jsonify({'error': 'нужны name и content'}), 400

    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute('SELECT id FROM templates WHERE name = ? AND id != ?', (data['name'], tid)).fetchone()
    if existing:
        conn.close()
        return jsonify({'error': 'имя уже занято', 'exists': True, 'id': existing[0]}), 409

    conn.execute('UPDATE templates SET name = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                 (data['name'], data['content'], tid))
    conn.commit()
    conn.close()
    return jsonify({'message': 'обновлено'})


@app.route('/templates/<int:tid>', methods=['DELETE'])
def delete_template(tid):
    """удалить шаблон"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('DELETE FROM templates WHERE id = ?', (tid,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'удалено'})


@app.route('/render/<int:tid>', methods=['POST'])
def render_pdf(tid):
    """сгенерировать PDF с подстановкой данных"""
    data = request.json or {}
    conn = sqlite3.connect(DB_PATH)
    t = conn.execute('SELECT content FROM templates WHERE id = ?', (tid,)).fetchone()
    conn.close()
    if not t:
        return jsonify({'error': 'шаблон не найден'}), 404

    html = substitute(t[0], data)
    pdf = to_pdf(html)
    return send_file(io.BytesIO(pdf), mimetype='application/pdf', as_attachment=True,
                     download_name=f'документ_{tid}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')


@app.route('/preview/<int:tid>', methods=['POST'])
def preview_html(tid):
    """показать HTML с подстановкой (без сохранения PDF)"""
    data = request.json or {}
    conn = sqlite3.connect(DB_PATH)
    t = conn.execute('SELECT content FROM templates WHERE id = ?', (tid,)).fetchone()
    conn.close()
    if not t:
        return jsonify({'error': 'шаблон не найден'}), 404

    html = substitute(t[0], data)
    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Предпросмотр</title>
    <style>
        body {{ font-family: 'Times New Roman', Times, serif; padding: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    </style>
</head>
<body>
{html}
</body>
</html>''', 200, {'Content-Type': 'text/html'}


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == '__main__':
    print()
    print('=' * 50)
    print('PDF Генератор запущен')
    print('=' * 50)
    print('Сервер: http://localhost:5000')
    print()
    print('API эндпоинты:')
    print('  GET  /')
    print('  GET  /templates')
    print('  POST /templates')
    print('  GET  /templates/{id}')
    print('  PUT  /templates/{id}')
    print('  DELETE /templates/{id}')
    print('  POST /render/{id}')
    print('  POST /preview/{id}')
    print()
    print('Нажмите Ctrl+C для остановки')
    print('=' * 50)
    print()

    app.run(debug=True, host='0.0.0.0', port=5000)
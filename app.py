from flask import Flask, render_template, jsonify
import psycopg2

app = Flask(__name__)

# Подключение к базе данных PostgreSQL
def get_db_connection():
    conn = psycopg2.connect(
        dbname="project",
        user="postgres",
        password="k8bdP2ht",
        host="localhost",
        port="5432"
    )
    return conn

# Маршрут для отображения главной страницы
@app.route('/')
def index():
    return render_template('index.html')

# Маршрут для получения данных в формате JSON
@app.route('/data')
def get_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT  discipline_id, SUM(ball)  FROM zhurnal_ocenok  where lichnost_guid = 'ee3f1a6b-8c7e-4d02-8d1b-91042600aed2' GROUP BY discipline_id;")  
    data = cursor.fetchall()
    cursor.close()
    conn.close()

    # Преобразование данных в формат JSON
    return jsonify(data)

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/autoriz')
def autoriz():
    return render_template('autoriz.html')
#@app.route('/data')
# def get_data():
#     # Временно возвращаем тестовые данные для проверки скорости
#     return jsonify([['Student1', 85], ['Student2', 90]])

if __name__ == '__main__':
    app.run(debug=True)

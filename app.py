from flask import Flask, render_template, request, jsonify
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

# Маршрут для получения данных по фильтру группы
@app.route('/filter_data')
def filter_data():
    group = request.args.get('group')  # Получаем выбранную группу из параметра запроса
    conn = get_db_connection()
    cursor = conn.cursor()

  # SELECT discipline_id, SUM(ball) 
    # FROM zhurnal_ocenok 
    # WHERE group_id = %s
    # GROUP BY discipline_id;
    # Запрос с фильтрацией по группе (при необходимости модифицируйте)

    # сейчас фильтрация работает для трех групп, выдает по группе гистограмму: студент - число пропусков (суммарное)
    query = """
    SELECT p.lichnost_guid, count(p.propusk), sum(z.ball)
	FROM public.propuski p
    join zhurnal_ocenok z on p.lichnost_guid = z.lichnost_guid
    where p.gruppa_guid = %s GROUP BY p.lichnost_guid;
    """
    cursor.execute(query, (group,))
    data = cursor.fetchall()

    cursor.close()
    conn.close()
    return jsonify(data)

# Пример маршрутов для других страниц
@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/autoriz')
def autoriz():
    return render_template('autoriz.html')

if __name__ == '__main__':
    app.run(debug=True)

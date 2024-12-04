from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_login import LoginManager, login_user, login_required, UserMixin
import psycopg2
import bcrypt
import secrets
import csv
import joblib
import pandas as pd
import numpy as np

app = Flask(__name__)
secret_key = secrets.token_hex(32)
app.secret_key = secret_key
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password  # Храним хеш пароля, а не сам пароль

    @staticmethod
    def get(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password FROM users WHERE id = %s', (user_id,))
        user_data = cursor.fetchone()
        hashed_password = bcrypt.hashpw(user_data[2].encode('utf-8'), bcrypt.gensalt())

        if user_data:
            return User(user_data[0], user_data[1], hashed_password)
        return None

    def is_active(self):
        return True

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
    return redirect(url_for('autoriz'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('index.html')

@app.route('/model')
#@login_required
def model():
    return render_template('model.html')

# Маршрут для получения данных по фильтру группы
@app.route('/filter_data')
def filter_data():
    group = request.args.get('group')  # Получаем выбранную группу из параметра запроса
    semester = request.args.get('semester')  # Получаем выбранный семестр из параметра запроса
    semester = int(semester) if semester else None

    conn = get_db_connection()
    cursor = conn.cursor()

    # Базовый SQL-запрос с фильтрацией
    query = """
    SELECT p.lichnost_guid, count(p.propusk), sum(z.ball)
    FROM public.propuski p
    JOIN zhurnal_ocenok z ON p.lichnost_guid = z.lichnost_guid
    WHERE (%s IS NULL OR p.gruppa_guid = %s)
    AND (%s IS NULL OR z.semester = %s)
    GROUP BY p.lichnost_guid;
    """

    # Выполнение запроса с учетом фильтров
    cursor.execute(query, (group, group, semester, semester))
    data = cursor.fetchall()
    print(type(data))
    cursor.close()
    conn.close()
    return jsonify(data)

@app.route('/model_data', methods=['POST'])
def model_data():
    group = request.args.get('group')  # Получаем выбранную группу из параметра запроса
    parameter = request.args.get('parameter')
    
    return process_data(model, group, parameter)


    # conn = get_db_connection()
    # cursor = conn.cursor()


    # query = """
    # SELECT * FROM public.magistri_s_ocenkami_pol_prichini_proryv
    # WHERE gruppa_guid = %s AND semestr = 1 AND god_rezultata is not null AND
    # prichina_otchisleniya_id is not null
    # GROUP BY p.lichnost_guid;
    # """
    # cursor.execute(query, (group, group))


    # data = cursor.fetchall()

    # cursor.close()
    # conn.close()
    #return jsonify(data)
    #return

# Пример маршрутов для других страниц
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        user_id = request.form['user_id']
        full_name = request.form['full_name']
        role = request.form['role']

        # Обновление данных пользователя
        cursor.execute('UPDATE users SET full_name = %s, role = %s WHERE id = %s',
                       (full_name, role, user_id))
        conn.commit()

    # Получение пользователей
    cursor.execute('SELECT id, full_name, username, role FROM users ORDER BY id')
    users = cursor.fetchall()

    cursor.close()
    conn.close()
    
    return render_template('admin.html', users=users)

@app.route('/autoriz', methods=['GET', 'POST'])
def autoriz():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, username, password, role FROM users WHERE username = %s', (username,))
        user_data = cursor.fetchone()
        hashed_password = bcrypt.hashpw(user_data[2].encode('utf-8'), bcrypt.gensalt())
        
        if user_data and bcrypt.checkpw(password.encode('utf-8'), hashed_password) and user_data[3] == 'Admin':
            user = User(user_data[0], user_data[1], hashed_password)
            login_user(user)
            flash('Вы успешно вошли в систему!', 'success')
            print(f'Пользователь {user_data[1]} вошёл')
            return redirect(url_for('dashboard'))  # Перенаправление на защищенную страницу
        elif user_data and bcrypt.checkpw(password.encode('utf-8'), hashed_password) and user_data[3] == 'User':
            flash('Недостаточно прав')
            print(f'У пользователя {user_data[1]} недостаточно прав')
        else:
            flash('Неверное имя пользователя или пароль')
            print('Пароль или имя введены неверно')

        cursor.close()
        conn.close()
        
    return render_template('autoriz.html')

def make_csv():
    with app.app_context():
        conn = get_db_connection()
        cursor = conn.cursor()

        # Базовый SQL-запрос с фильтрацией
        query = """
        SELECT * FROM public.magistri_s_ocenkami_pol_prichini_proryv
        WHERE semestr = 1 and god_rezultata is not null and 
        prichina_otchisleniya_id is not null;
        """
        cursor.execute(query)
        data = cursor.fetchall()

        columns = [description[0] for description in cursor.description]
        
        with open('magistri.csv', 'w', newline="", encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(columns)
            writer.writerows(data)

        cursor.close()
        conn.close()

        return 0

def process_data(model, group, parameter):
    with app.app_context():
        df = pd.read_csv('magistri_s_ocenkami_pol_prichini_proryv_only_1_semestr.csv')

        def replace_outliers(row):
            if row['ball'] > 100:
                if row['vid_att'] == 'Зачет':
                    return 55
                else:
                    return 100
            return row['ball']

        df['ball'] = df.apply(replace_outliers, axis=1)

        mean_scores = df.groupby('lichnost_guid')['ball'].mean()
        # Замена пропущенных значений на средние баллы
        df['ball'] = df.apply(lambda row: mean_scores[row['lichnost_guid']] if pd.isnull(row['ball']) else row['ball'], axis=1)
        df['ball'].fillna(0, inplace=True)
        df = df.drop_duplicates()
        df['data_nachala_obucheniya'] = pd.to_datetime(df['data_nachala_obucheniya']).dt.year
        df = df.drop(['id_obr', 'semestr', 'kurs_obucheniya', 'vid_att', 'ist_ocenki_id', 'forma_obucheniya_id'], axis=1)
        
        df = df.groupby('lichnost_guid').agg({
            'gruppa_guid': lambda x: x.iloc[0],
            'kod_napr_podgotovki': lambda x: x.iloc[0],
            'tip_fin_id': lambda x: x.iloc[0],
            'data_nachala_obucheniya': lambda x: x.iloc[0],
            'ball': 'mean',
            'god_rozhdeniya': lambda x: list(set(x)),
            'pol_id': lambda x: list(set(x)),
            'prichina_otchisleniya_id': lambda x: list(set(x)),
            'god_rezultata': lambda x: list(set(x)),
            'specialnost_id': lambda x: list(set(x)),
            'status_podtverzhden_id': lambda x: list(set(x)),
            'ball_proryv': lambda x: list(set(x))
        }).reset_index()

        df = df.explode('prichina_otchisleniya_id').explode('god_rozhdeniya').explode('pol_id').explode('god_rezultata').explode('specialnost_id').explode('status_podtverzhden_id').explode('ball_proryv')
        
        df['god_rozhdeniya'] = df['god_rozhdeniya'].astype(int)
        df['pol_id'] = df['pol_id'].astype(int)
        df['god_rezultata'] = df['god_rezultata'].astype(int)
        df['ball_proryv'] = df['ball_proryv'].astype(int)
        df['god_rozhdeniya'] = df['god_rozhdeniya'].astype(int)

        df = pd.get_dummies(df, columns=['prichina_otchisleniya_id', 'kod_napr_podgotovki', 'tip_fin_id', 'specialnost_id', 'status_podtverzhden_id'])
        #print(df.info())
        input_data = df[df['gruppa_guid'] == group][['data_nachala_obucheniya',
                    'ball',
                    'god_rozhdeniya',
                    'pol_id',
                    'god_rezultata', 
                    'ball_proryv',
                    'kod_napr_podgotovki_09.04.01',
                    'kod_napr_podgotovki_09.04.02', 
                    'kod_napr_podgotovki_09.04.04', 
                    'kod_napr_podgotovki_15.04.04', 
                    'kod_napr_podgotovki_15.04.06', 
                    'tip_fin_id_2', 
                    'tip_fin_id_3', 
                    'tip_fin_id_5', 
                    'specialnost_id_10662', 
                    'specialnost_id_10686', 
                    'specialnost_id_10687', 
                    'specialnost_id_10688',
                    'specialnost_id_10689', 
                    'specialnost_id_10698', 
                    'specialnost_id_10701', 
                    'specialnost_id_10704',
                    'specialnost_id_10708', 
                    'specialnost_id_10710', 
                    'specialnost_id_10711', 
                    'specialnost_id_10715',
                    'specialnost_id_10716', 
                    'specialnost_id_10746', 
                    'specialnost_id_10792',
                    'specialnost_id_17206',
                    'specialnost_id_17882',
                    'specialnost_id_18036',
                    'specialnost_id_18040',
                    'specialnost_id_18044',
                    'specialnost_id_18045',
                    'specialnost_id_18052',
                    'specialnost_id_18054', 
                    'specialnost_id_18062', 
                    'specialnost_id_18078', 
                    'specialnost_id_18079', 
                    'specialnost_id_19159',
                    'specialnost_id_19678',
                    'specialnost_id_20017', 
                    'specialnost_id_20018', 
                    'specialnost_id_20020', 
                    'specialnost_id_20022', 
                    'specialnost_id_20030', 
                    'specialnost_id_20467', 
                    'specialnost_id_20468', 
                    'specialnost_id_20469', 
                    'specialnost_id_21050', 
                    'specialnost_id_21082', 
                    'specialnost_id_21794', 
                    'specialnost_id_21911', 
                    'status_podtverzhden_id_2',
                    'status_podtverzhden_id_6']].head(1)
        
        

        predictions = model.predict(input_data)
        probs = model.predict_proba(input_data)

        prediction = predictions[0]
        predicted_probability = probs[parameter]
        

# Формируем результат, передаем только вероятности для класса 1
        # result = {
        #     "class_1_probabilities": probabilities_for_class_1.tolist(),
        #     "parameter": int(parameter + 1)
        # }
        # Формируем результат
        # result = np.array([
        #     int(parameter + 1), 
        #     predicted_probability[:,1]])  # +1 для преобразования индекса в класс (если классы начинаются с 1)
        
        

        print("Предсказание для первой строки:", prediction)
        print("Вероятности:", probs)
        # print("Результат:", int(result[0]), "с вероятностью", result[1])
        print((predicted_probability))
        # result = [[row[1] for row in arr.tolist()] for arr in result]
        second_columns = [arr[:, 1] for arr in probs]
        second_columns_as_list = [arr.tolist() for arr in second_columns]
        print(jsonify(second_columns_as_list))

        return jsonify(second_columns_as_list)
        


if __name__ == '__main__':
    model = joblib.load('regression_new.joblib')
    data_json = process_data(model, '8ec18395-db35-4ffa-b7c5-ab1d03d488c1', 2)
    app.run(debug=True)

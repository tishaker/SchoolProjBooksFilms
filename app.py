from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime

from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'


def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0
            )
        ''')
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'avatar' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT NULL')
    if 'is_admin' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0')

    admin_password = generate_password_hash('admin1234')
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, email, password, is_admin)
        VALUES (?, ?, ?, 1)
    ''', ('admin', 'admin@site.local', admin_password))

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            movie_title TEXT NOT NULL,
            content TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 10),
            status TEXT DEFAULT "pending",
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            review_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, review_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (review_id) REFERENCES reviews(id)  
        )
    ''')
    conn.commit()
    conn.close()


def migrate_likes_table():
    """Пересоздаём таблицу лайков для рецензий."""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS likes")

    cursor.execute('''
        CREATE TABLE likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            review_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, review_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (review_id) REFERENCES reviews(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Таблица likes пересоздана!")

def upgrade_db():
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(books)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'has_movie_adaptation' not in columns:
            cursor.execute('ALTER TABLE books ADD COLUMN has_movie_adaptation BOOLEAN DEFAULT FALSE')
            print("Добавлен столбец has_movie_adaptation")

        if 'movie_adaptation_title' not in columns:
            cursor.execute('ALTER TABLE books ADD COLUMN movie_adaptation_title TEXT')
            print("Добавлен столбец movie_adaptation_title")

        if 'theme' not in columns:
            cursor.execute('ALTER TABLE books ADD COLUMN theme TEXT')
            print("Добавлен столбец theme")

        cursor.execute("PRAGMA table_info(movies)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'based_on_book_id' not in columns:
            cursor.execute('ALTER TABLE movies ADD COLUMN based_on_book_id INTEGER')
            print("Добавлен столбец based_on_book_id")

        if 'theme' not in columns:
            cursor.execute('ALTER TABLE movies ADD COLUMN theme TEXT')
            print("Добавлен столбец theme")

        conn.commit()

        cursor.execute("""
            UPDATE books 
            SET has_movie_adaptation = 1,
                movie_adaptation_title = CASE 
                    WHEN title = 'Война и мир' THEN 'Война и мир (1966)'
                    WHEN title = 'Преступление и наказание' THEN 'Преступление и наказание (1969)'
                    WHEN title = '1984' THEN '1984 (1984)'
                    WHEN title = 'Гарри Поттер и философский камень' THEN 'Гарри Поттер и философский камень (2001)'
                    WHEN title = 'Властелин колец: Братство Кольца' THEN 'Властелин колец: Братство Кольца (2001)'
                    WHEN title = 'Зелёная миля' THEN 'Зелёная миля (1999)'
                    WHEN title = 'Код да Винчи' THEN 'Код да Винчи (2006)'
                    WHEN title = 'Убийство в "Восточном экспрессе"' THEN 'Убийство в "Восточном экспрессе" (1974)'
                    ELSE NULL
                END
        """)

        conn.commit()
        print("Данные успешно обновлены")

    except Exception as e:
        print(f"Ошибка при обновлении базы: {e}")
    finally:
        conn.close()


def init_library_db():
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS authors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            birth_year INTEGER,
            death_year INTEGER,
            country TEXT,
            bio TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS genres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author_id INTEGER,
            year INTEGER,
            genre_id INTEGER,
            summary TEXT,
            rating REAL DEFAULT 0.0,
            icon_emoji TEXT DEFAULT '📚',
            theme TEXT,
            has_movie_adaptation BOOLEAN DEFAULT FALSE,
            movie_adaptation_title TEXT,
            FOREIGN KEY (author_id) REFERENCES authors(id),
            FOREIGN KEY (genre_id) REFERENCES genres(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            director TEXT,
            year INTEGER,
            genre_id INTEGER,
            summary TEXT,
            rating REAL DEFAULT 0.0,
            duration INTEGER,
            icon_emoji TEXT DEFAULT '🎬',
            theme TEXT,
            based_on_book_id INTEGER,
            FOREIGN KEY (genre_id) REFERENCES genres(id),
            FOREIGN KEY (based_on_book_id) REFERENCES books(id)
        )
    ''')

    cursor.execute('SELECT COUNT(*) FROM genres')
    if cursor.fetchone()[0] == 0:
        genres_data = [
            ('Драма', 'Произведения с серьёзным сюжетом'),
            ('Фантастика', 'Литература о вымышленных технологиях и мирах'),
            ('Роман', 'Большое повествовательное произведение'),
            ('Приключения', 'Захватывающие истории о путешествиях'),
            ('Детектив', 'Произведения о расследовании преступлений'),
            ('Комедия', 'Юмористические произведения'),
            ('Триллер', 'Напряженные истории с элементами саспенса'),
            ('Исторический', 'Произведения на исторические темы')
        ]
        cursor.executemany('INSERT INTO genres (name, description) VALUES (?, ?)', genres_data)

        authors_data = [
            ('Лев Толстой', 1828, 1910, 'Россия', 'Один из величайших писателей мира'),
            ('Фёдор Достоевский', 1821, 1881, 'Россия', 'Классик русской литературы'),
            ('Джордж Оруэлл', 1903, 1950, 'Великобритания', 'Автор антиутопий'),
            ('Дж. К. Роулинг', 1965, None, 'Великобритания', 'Автор серии о Гарри Поттере'),
            ('Джон Толкин', 1892, 1973, 'Великобритания', 'Автор "Властелина Колец"'),
            ('Стивен Кинг', 1947, None, 'США', 'Король ужасов'),
            ('Дэн Браун', 1964, None, 'США', 'Автор интеллектуальных триллеров'),
            ('Агата Кристи', 1890, 1976, 'Великобритания', 'Королева детектива')
        ]
        cursor.executemany('INSERT INTO authors (name, birth_year, death_year, country, bio) VALUES (?, ?, ?, ?, ?)',
                           authors_data)

        books_data = [
            ('Война и мир', 1, 1869, 1,
             'Эпический роман о русском обществе во время наполеоновских войн. Сложные судьбы героев на фоне исторических событий.',
             4.9, '👑', 'классика', True, 'Война и мир (1966)'),
            ('Преступление и наказание', 2, 1866, 1,
             'Роман о бывшем студенте Родионе Раскольникове, совершившем убийство ради идеи.', 4.8, '⚖️', 'классика',
             True, 'Преступление и наказание (1969)'),
            ('1984', 3, 1949, 2, 'Антиутопия о тоталитарном обществе под наблюдением Большого Брата.', 4.7, '👁️',
             'антиутопия', True, '1984 (1984)'),
            ('Гарри Поттер и философский камень', 4, 1997, 2,
             'Первая книга о юном волшебнике Гарри Поттере, открывающем магический мир.', 4.9, '⚡', 'фэнтези', True,
             'Гарри Поттер и философский камень (2001)'),
            ('Властелин колец: Братство Кольца', 5, 1954, 2,
             'Первая часть трилогии о путешествии хоббита Фродо Бэггинса.', 4.8, '💍', 'фэнтези', True,
             'Властелин колец: Братство Кольца (2001)'),
            ('Зелёная миля', 6, 1996, 1, 'История о заключенном с магическими способностями в тюрьме смертников.', 4.7,
             '👣', 'драма', True, 'Зелёная миля (1999)'),
            ('Код да Винчи', 7, 2003, 6, 'Интеллектуальный триллер о поисках Святого Грааля.', 4.5, '🔑', 'триллер', True,
             'Код да Винчи (2006)'),
            ('Убийство в "Восточном экспрессе"', 8, 1934, 5,
             'Знаменитый детектив Эркюля Пуаро расследует убийство в поезде.', 4.6, '🔍', 'детектив', True,
             'Убийство в "Восточном экспрессе" (1974)')
        ]
        cursor.executemany(
            'INSERT INTO books (title, author_id, year, genre_id, summary, rating, icon_emoji, theme, has_movie_adaptation, movie_adaptation_title) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            books_data)

        movies_data = [
            ('Война и мир (1966)', 'Сергей Бондарчук', 1966, 1,
             'Масштабная экранизация романа Толстого, получившая "Оскар".', 4.8, 431, '🎬', 'классика', 1),
            ('Преступление и наказание (1969)', 'Лев Кулиджанов', 1969, 1, 'Советская экранизация романа Достоевского.',
             4.7, 211, '⚖️', 'классика', 2),
            ('1984 (1984)', 'Майкл Редфорд', 1984, 2, 'Экранизация антиутопии Оруэлла с Джоном Хёртом.', 4.6, 113, '👁️',
             'антиутопия', 3),
            ('Гарри Поттер и философский камень (2001)', 'Крис Коламбус', 2001, 2,
             'Первая часть киносаги о юном волшебнике.', 4.8, 152, '⚡', 'фэнтези', 4),
            ('Властелин колец: Братство Кольца (2001)', 'Питер Джексон', 2001, 2,
             'Эпическая экранизация первой части трилогии Толкина.', 4.9, 178, '💍', 'фэнтези', 5),
            ('Зелёная миля (1999)', 'Фрэнк Дарабонт', 1999, 1, 'Экранизация романа Стивена Кинга с Томом Хэнксом.', 4.8,
             189, '👣', 'драма', 6),
            ('Код да Винчи (2006)', 'Рон Ховард', 2006, 6, 'Экранизация бестселлера Дэна Брауна с Томом Хэнксом.', 4.3,
             149, '🔑', 'триллер', 7),
            ('Убийство в "Восточном экспрессе" (1974)', 'Сидни Люмет', 1974, 5,
             'Классическая экранизация детектива Агаты Кристи.', 4.7, 128, '🔍', 'детектив', 8)
        ]
        cursor.executemany(
            'INSERT INTO movies (title, director, year, genre_id, summary, rating, duration, icon_emoji, theme, based_on_book_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            movies_data)

    conn.commit()
    conn.close()


@app.route('/')
def index():
    search_query = request.args.get('search', '')
    results = []

    if search_query:
        conn = sqlite3.connect('library.db')
        cursor = conn.cursor()

        cursor.execute('''
            SELECT b.title, a.name, b.summary, b.icon_emoji, 'book' as type
            FROM books b
            JOIN authors a ON b.author_id = a.id
            WHERE b.title LIKE ? OR a.name LIKE ?
            LIMIT 5
        ''', (f'%{search_query}%', f'%{search_query}%'))
        book_results = cursor.fetchall()

        cursor.execute('''
            SELECT title, director, summary, icon_emoji, 'movie' as type
            FROM movies
            WHERE title LIKE ? OR director LIKE ?
            LIMIT 5
        ''', (f'%{search_query}%', f'%{search_query}%'))
        movie_results = cursor.fetchall()

        conn.close()
        results = book_results + movie_results

    return render_template('index.html', search_query=search_query, search_results=results)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if username.lower() == 'admin':
            flash('Это имя пользователя зарезервировано!', 'error')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Пароли не совпадают!', 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        try:
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, hashed_password)
            )
            conn.commit()
            conn.close()

            flash('Регистрация успешна! Теперь вы можете войти.', 'success')
            return redirect(url_for('login'))

        except sqlite3.IntegrityError:
            flash('Пользователь с таким именем или email уже существует!', 'error')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, email, password, avatar, is_admin FROM users WHERE username = ?',
                       (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['is_admin'] = bool(user[5]) if len(user) > 5 else False
            flash(f'Добро пожаловать, {username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль!', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index'))


@app.route('/top-month')
def top_month():
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(books)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'has_movie_adaptation' in columns:
            cursor.execute('''
                SELECT b.title, a.name, b.year, b.rating, b.icon_emoji, 
                       b.summary, m.title as movie_title, m.year as movie_year
                FROM books b
                JOIN authors a ON b.author_id = a.id
                LEFT JOIN movies m ON b.id = m.based_on_book_id
                WHERE b.has_movie_adaptation = 1
                ORDER BY b.rating DESC
                LIMIT 8
            ''')
        else:
            cursor.execute('''
                SELECT b.title, a.name, b.year, b.rating, b.icon_emoji, 
                       b.summary, m.title as movie_title, m.year as movie_year
                FROM books b
                JOIN authors a ON b.author_id = a.id
                LEFT JOIN movies m ON b.id = m.based_on_book_id
                WHERE m.based_on_book_id IS NOT NULL
                ORDER BY b.rating DESC
                LIMIT 8
            ''')

        top_books = cursor.fetchall()

    except Exception as e:
        print(f"Ошибка при выполнении запроса: {e}")
        top_books = []

    cursor.execute('''
        SELECT m.title, m.director, m.year, m.rating, m.icon_emoji, 
               m.summary, b.title as book_title
        FROM movies m
        LEFT JOIN books b ON m.based_on_book_id = b.id
        ORDER BY m.rating DESC
        LIMIT 8
    ''')
    top_movies = cursor.fetchall()

    conn.close()

    return render_template('top_month.html',
                           top_books=top_books,
                           top_movies=top_movies)


@app.route('/genres')
def genres():
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT g.name, g.description, 
               (SELECT title FROM books WHERE genre_id = g.id LIMIT 1) as book_example,
               (SELECT title FROM movies WHERE genre_id = g.id LIMIT 1) as movie_example,
               COUNT(DISTINCT b.id) as book_count,
               COUNT(DISTINCT m.id) as movie_count
        FROM genres g
        LEFT JOIN books b ON g.id = b.genre_id
        LEFT JOIN movies m ON g.id = m.genre_id
        GROUP BY g.id
        ORDER BY g.name
    ''')
    genres_data = cursor.fetchall()

    conn.close()

    return render_template('genres.html', genres_data=genres_data)


@app.route('/best-all-time')
def best_all_time():
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT b.title, a.name, b.year, b.rating, b.icon_emoji, 
               b.summary, m.title as movie_title, m.year as movie_year,
               m.rating as movie_rating
        FROM books b
        JOIN authors a ON b.author_id = a.id
        LEFT JOIN movies m ON b.id = m.based_on_book_id
        WHERE b.year < 1950 OR b.rating >= 4.5
        ORDER BY b.rating DESC
        LIMIT 10
    ''')
    classic_books = cursor.fetchall()

    cursor.execute('''
        SELECT m.title, m.director, m.year, m.rating, m.icon_emoji, 
               m.summary, b.title as based_on_book
        FROM movies m
        LEFT JOIN books b ON m.based_on_book_id = b.id
        WHERE m.year < 2000 OR m.rating >= 4.5
        ORDER BY m.rating DESC
        LIMIT 10
    ''')
    classic_movies = cursor.fetchall()

    conn.close()

    return render_template('best_all_time.html',
                           classic_books=classic_books,
                           classic_movies=classic_movies)


@app.route('/space-theme')
def space_theme():
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT b.title, a.name, b.year, b.summary, b.icon_emoji, b.rating
        FROM books b
        JOIN authors a ON b.author_id = a.id
        WHERE b.theme = 'космос' OR b.title LIKE '%космос%' OR b.summary LIKE '%космос%'
        ORDER BY b.rating DESC
        LIMIT 10
    ''')
    space_books = cursor.fetchall()

    cursor.execute('''
        SELECT title, director, year, summary, icon_emoji, rating
        FROM movies
        WHERE theme = 'космос' OR title LIKE '%космос%' OR summary LIKE '%космос%'
        ORDER BY rating DESC
        LIMIT 10
    ''')
    space_movies = cursor.fetchall()

    conn.close()

    return render_template('space_theme.html',
                           space_books=space_books,
                           space_movies=space_movies)


@app.route('/profiles/<username>')
def profile(username):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('SELECT id, avatar FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    if not user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('index'))
    user_id = user[0]
    avatar = user[1]

    cursor.execute('''
        SELECT COUNT(*) FROM reviews 
        WHERE user_id = ? AND status = 'approved'
    ''', (user_id,))
    reviews_count = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) 
        FROM likes l
        JOIN reviews r ON l.review_id = r.id
        WHERE r.user_id = ? AND r.status = 'approved'
    ''', (user_id,))
    total_likes = cursor.fetchone()[0]

    cursor.execute('''
        SELECT DATE(created_at) as day, COUNT(*) as count
        FROM user_activity
        WHERE user_id = ? AND created_at >= DATE('now', '-6 days')
        GROUP BY day ORDER BY day
    ''', (user_id,))
    raw_activity = dict(cursor.fetchall())

    from datetime import date, timedelta
    activity_data = []
    for i in range(6, -1, -1):
        day = (date.today() - timedelta(days=i)).isoformat()
        activity_data.append({'day': day, 'count': raw_activity.get(day, 0)})

    cursor.execute('''
        SELECT content, created_at FROM comments
        WHERE user_id = ? ORDER BY created_at DESC LIMIT 5
    ''', (user_id,))
    comments = cursor.fetchall()

    conn.close()

    return render_template('profile.html',
                           username=username,
                           avatar=avatar,
                           activity_data=activity_data,
                           comments=comments,
                           likes_count=total_likes,
                           reviews_count=reviews_count)


UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/profiles/<username>/upload-avatar', methods=['POST'])
def upload_avatar(username):
    if session.get('username') != username:
        flash('Нет доступа', 'error')
        return redirect(url_for('profile', username=username))

    if 'avatar' not in request.files:
        flash('Файл не выбран', 'error')
        return redirect(url_for('profile', username=username))

    file = request.files['avatar']

    if file.filename == '':
        flash('Файл не выбран', 'error')
        return redirect(url_for('profile', username=username))

    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f'avatar_{username}.{ext}')
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET avatar = ? WHERE username = ?',
                       (filename, username))
        conn.commit()
        conn.close()

        flash('Аватар обновлён!', 'success')
    else:
        flash('Недопустимый формат файла', 'error')

    return redirect(url_for('profile', username=username))



@app.route('/reviews')
def reviews():
    """Лента одобренных рецензий."""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.id, u.username, u.avatar, r.movie_title,
               r.content, r.rating, r.approved_at,
               (SELECT COUNT(*) FROM likes WHERE review_id = r.id) as likes_count
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.status = "approved"
        ORDER BY r.approved_at DESC
    ''')
    approved = cursor.fetchall()
    conn.close()
    return render_template('reviews.html', reviews=approved)


@app.route('/reviews/submit', methods=['GET', 'POST'])
def submit_review():
    """Форма подачи рецензии пользователем."""
    if 'user_id' not in session:
        flash('Войдите в аккаунт, чтобы оставить рецензию.', 'error')
        return redirect(url_for('login'))
    if session.get('is_admin'):
        flash('Администратор не может подавать рецензии.', 'error')
        return redirect(url_for('reviews'))

    if request.method == 'POST':
        movie_title = request.form.get('movie_title', '').strip()
        content = request.form.get('content', '').strip()
        try:
            rating = int(request.form.get('rating', 0))
        except ValueError:
            rating = 0

        if not movie_title or not content or not (1 <= rating <= 10):
            flash('Заполните все поля корректно (оценка от 1 до 10).', 'error')
            return redirect(url_for('submit_review'))

        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reviews (user_id, movie_title, content, rating)
            VALUES (?, ?, ?, ?)
        ''', (session['user_id'], movie_title, content, rating))
        conn.commit()
        conn.close()
        flash('Рецензия отправлена на модерацию!', 'success')
        return redirect(url_for('reviews'))

    return render_template('submit_review.html')


@app.route('/admin/reviews')
def admin_reviews():
    """Панель модерации — только для админа."""
    if not session.get('is_admin'):
        flash('Доступ запрещён.', 'error')
        return redirect(url_for('index'))

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.id, u.username, r.movie_title, r.content,
               r.rating, r.status, r.created_at
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        ORDER BY CASE r.status WHEN "pending" THEN 0 ELSE 1 END, r.created_at DESC
    ''')
    all_reviews = cursor.fetchall()
    conn.close()
    return render_template('admin_reviews.html', reviews=all_reviews)


@app.route('/admin/reviews/<int:review_id>/<action>', methods=['POST'])
def admin_review_action(review_id, action):
    """Принять или отклонить рецензию."""
    if not session.get('is_admin'):
        flash('Доступ запрещён.', 'error')
        return redirect(url_for('index'))

    if action not in ('approve', 'reject'):
        flash('Неизвестное действие.', 'error')
        return redirect(url_for('admin_reviews'))

    new_status = 'approved' if action == 'approve' else 'rejected'
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    if new_status == 'approved':
        cursor.execute('''
            UPDATE reviews SET status = "approved",
                               approved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (review_id,))
    else:
        cursor.execute('UPDATE reviews SET status = "rejected" WHERE id = ?', (review_id,))
    conn.commit()
    conn.close()

    flash('Статус рецензии обновлён.', 'success')
    return redirect(url_for('admin_reviews'))


@app.route('/review/<int:review_id>/like', methods=['POST'])
def like_review(review_id):
    """Поставить/убрать лайк рецензии."""
    if 'user_id' not in session:
        return {'error': 'Войдите в аккаунт'}, 401

    user_id = session['user_id']

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM reviews WHERE id = ? AND status = "approved"', (review_id,))
    if not cursor.fetchone():
        conn.close()
        return {'error': 'Рецензия не найдена'}, 404

    try:
        cursor.execute('INSERT INTO likes (user_id, review_id) VALUES (?, ?)', (user_id, review_id))
        conn.commit()
        cursor.execute('SELECT COUNT(*) FROM likes WHERE review_id = ?', (review_id,))
        likes_count = cursor.fetchone()[0]
        conn.close()
        return {'success': True, 'likes': likes_count}

    except sqlite3.IntegrityError:
        cursor.execute('DELETE FROM likes WHERE user_id = ? AND review_id = ?', (user_id, review_id))
        conn.commit()
        cursor.execute('SELECT COUNT(*) FROM likes WHERE review_id = ?', (review_id,))
        likes_count = cursor.fetchone()[0]
        conn.close()
        return {'success': True, 'likes': likes_count, 'removed': True}


@app.route('/review/<int:review_id>/likes')
def get_review_likes(review_id):
    """Получить количество лайков рецензии."""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM likes WHERE review_id = ?', (review_id,))
    likes = cursor.fetchone()[0]

    user_liked = False
    if 'user_id' in session:
        cursor.execute('SELECT 1 FROM likes WHERE review_id = ? AND user_id = ?',
                       (review_id, session['user_id']))
        user_liked = cursor.fetchone() is not None

    conn.close()
    return {'likes': likes, 'user_liked': user_liked}


if __name__ == '__main__':
    init_db()
    init_library_db()
    upgrade_db()
    migrate_likes_table()
    app.run(debug=True, port=8001)
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__, static_folder='static')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'  # Add a secret key for session management
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    todos = db.relationship('Todo', backref='user', lazy=True)

class Todo(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    desc = db.Column(db.String(500), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_done = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(10), nullable=False, default='Medium')

    def formatted_date(self):
        return self.date_created.strftime("%B %d, %Y")

    def formatted_due_date(self):
        return self.due_date.strftime("%B %d, %Y") if self.due_date else "No due date"

    def __repr__(self):
        return f"{self.sno} - {self.title}"

@app.route('/toggle_done/<int:todo_id>', methods=['POST'])
@login_required
def toggle_done(todo_id):
    todo = Todo.query.get(todo_id)
    if todo and todo.user_id == current_user.id:
        todo.is_done = not todo.is_done
        db.session.commit()
        return jsonify(success=True)
    return jsonify(success=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/update_priority/<int:sno>', methods=['POST'])
@login_required
def update_priority(sno):
    todo = Todo.query.filter_by(sno=sno, user_id=current_user.id).first()
    if not todo:
        return jsonify({'success': False}), 404
    
    data = request.json
    new_priority = data.get('priority')
    
    if new_priority:
        todo.priority = new_priority
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False}), 400

@app.route('/update_due_date/<int:todo_id>', methods=['POST'])
@login_required
def update_due_date(todo_id):
    todo = Todo.query.get_or_404(todo_id)
    data = request.get_json()
    due_date_str = data.get('due_date')
    if due_date_str:
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        todo.due_date = due_date
    else:
        todo.due_date = None
    db.session.commit()
    return jsonify(success=True)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Check if username or email already exists
        user_exists = User.query.filter_by(username=username).first()
        email_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('register'))
        if email_exists:
            flash('Email already exists. Please use a different one.', 'danger')
            return redirect(url_for('register'))

        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'danger')
            return redirect(url_for('register'))

        # Create new user
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        flash('Registration successful! You are now logged in.', 'success')
        return redirect(url_for('hello_world'))
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('hello_world'))
        else:
            flash('Login unsuccessful. Check username and password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/search', methods=['GET'])
@login_required
def search():
    search_query = request.args.get('search_query', '')
    if search_query:
        # Perform search query based on current_user.id and search_query
        filtered_todos = Todo.query.filter(
            Todo.user_id == current_user.id,
            (Todo.title.contains(search_query)) | (Todo.desc.contains(search_query))
        ).all()
    else:
        filtered_todos = []

    return render_template('search_results.html', filtered_todos=filtered_todos, search_query=search_query)

@app.route('/filter', methods=['GET'])
@login_required
def filter_todos():
    filter_option = request.args.get('filter', 'all')
    if filter_option == 'due_date':
        allTodo = Todo.query.filter_by(user_id=current_user.id).order_by(Todo.due_date.asc()).all()
    elif filter_option == 'priority':
        allTodo = Todo.query.filter_by(user_id=current_user.id).order_by(
            db.case(
                (Todo.priority == 'high', 1),
                (Todo.priority == 'medium', 2),
                (Todo.priority == 'low', 3),
                else_=4
            )
        ).all()
    elif filter_option == 'done':
        allTodo = Todo.query.filter_by(user_id=current_user.id, is_done=True).all()
    elif filter_option == 'not_done':
        allTodo = Todo.query.filter_by(user_id=current_user.id, is_done=False).all()
    else:
        allTodo = Todo.query.filter_by(user_id=current_user.id).all()
    return render_template('index.html', allTodo=allTodo)


@app.route('/', methods=['GET', 'POST'])
@login_required
def hello_world():
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['desc']
        todo = Todo(title=title, desc=desc, user_id=current_user.id)
        db.session.add(todo)
        db.session.commit()

    allTodo = Todo.query.filter_by(user_id=current_user.id).all()
    return render_template('index.html', allTodo=allTodo)


@app.route('/update/<int:sno>', methods=['GET', 'POST'])
@login_required
def update(sno):
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['desc']
        todo = Todo.query.filter_by(sno=sno).first()
        todo.title = title
        todo.desc = desc
        db.session.commit()
        return redirect("/")
    
    todo = Todo.query.filter_by(sno=sno).first()
    return render_template('update.html', todo=todo)

@app.route('/delete/<int:sno>')
@login_required
def delete(sno):
    todo = Todo.query.filter_by(sno=sno).first()
    db.session.delete(todo)
    db.session.commit()
    return redirect('/')

@app.route('/about')
def about():
    return render_template('about.html')


if __name__ == "__main__":
    app.run(debug=True, port=8000)

from flask import Flask, request, redirect, url_for, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_admin import Admin, BaseView, expose, AdminIndexView
from flask_admin.menu import MenuLink
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import Select2TagsField
from wtforms import SelectMultipleField
from wtforms.fields import StringField
from wtforms.widgets import TextArea
from wtforms.fields import SelectMultipleField
from flask_admin.form import Select2Field
from datetime import datetime, timedelta
import bcrypt
import secrets

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
app.secret_key = 'LAB8'
login_manager.session_protection = "strong"
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(seconds=30)

class User(db.Model, UserMixin):
    __tablename__= "users"
    id = db.Column(db.Integer, primary_key=True, unique=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default="Student")
    def get_grade(self, student_id, course_id):
        #original code
        #grade = Grade.query.filter_by(student_id=student_id, course_id=course_id).first() 
        #return grade.value

        #new additions to account for bug when adding new user through admin in course
        grade = Grade.query.filter_by(student_id=student_id, course_id=course_id).first() 
        if grade:
            return grade.value
        else:
            base_grade_value = 0.0  
            base_grade = Grade(student_id=student_id, course_id=course_id, value=base_grade_value)
            db.session.add(base_grade)
            db.session.commit()
            return base_grade_value

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True, unique=True)
    name = db.Column(db.String(100), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=10)
    teachers = db.relationship("User", secondary="teacher_course_association", backref="courses_taught", lazy=True)
    students = db.relationship("User", secondary="course_enrollment", backref="courses_enrolled", lazy=True)
    #added cascade='all, delete-orphan'
    grades = db.relationship("Grade", backref="course", lazy=True, overlaps="course,grades", cascade='all, delete-orphan')
    
class Grade(db.Model):
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True, unique=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    value = db.Column(db.Float, nullable=False)

    c = db.relationship('Course', backref='course_grades', lazy=True, overlaps="course_grades")
    s = db.relationship('User', backref='grades', lazy=True, overlaps="course_grades")

class CourseEnrollment(db.Model):
    __tablename__ = 'course_enrollment'
    id = db.Column(db.Integer, primary_key=True, unique=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

teacher_course_association = db.Table('teacher_course_association',
    db.Column('teacher_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('course_id', db.Integer, db.ForeignKey('courses.id'))
)

class UserView(ModelView):
    form_excluded_columns = ['id', 'password']
    column_list = ['username', 'role', 'courses']

    def _get_course_names(self, user):
        if user.role == "Teacher":
            courses = user.courses_taught
        else:
            courses = user.courses_enrolled
        all_course_names = ', '.join([course.name for course in courses])
        return all_course_names

    column_formatters = {
        'courses': lambda v, c, m, p: v._get_course_names(m),
        'role': lambda v, c, m, p: m.role
    }

class CourseView(ModelView):
    form_excluded_columns = ['id', 'teachers', 'students', 'grades', 'course_grades']
    column_list = ['name', 'time', 'capacity', 'teachers', 'students']
    def _get_teacher_names(self, context, model, name):
        teachers = getattr(model, 'teachers', [])
        return ', '.join([teacher.username for teacher in teachers])

    def _get_student_names(self, context, model, name):
        students = getattr(model, 'students', [])
        return ', '.join([student.username for student in students])
                
    column_formatters = {
        'teachers': _get_teacher_names,
        'students': _get_student_names
    }

    #Calculate and update the new capacity of the course 
    #You have to set it back to orginal capacity before saving can be removed if wanted
    def on_model_change(self, form, model, is_created):
        super().on_model_change(form, model, is_created)
        if 'students' in form.data:
            new_capacity = model.capacity - len(form.data['students'])
            model.capacity = new_capacity
            db.session.commit()

class GradeView(ModelView):
    form_excluded_columns = ['id', 'course_id', 'student_id']
    column_list = ['course_name', 'student_username', 'value']

    def course_name(self, context, model, name):
        return model.c.name if model.c else "N/A"

    def student_username(self, context, model, name):
        return model.s.username if model.s else "N/A"
    
    column_formatters = {
        'course_name': course_name,
        'student_username': student_username
    }
class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        if current_user.role != 'Admin':
            return redirect(url_for("home"))
        return redirect(url_for('user.index_view'))

    @expose('/login')
    def login_view(self):
        return redirect(url_for("login"))
    
class MyLogoutMenuLink(MenuLink):
    def get_url(self):
        return url_for('logout')
    
admin = Admin(app, index_view=MyAdminIndexView())
admin._menu = admin._menu[1:]
admin.add_view(UserView(User, db.session))
admin.add_view(CourseView(Course, db.session))
admin.add_view(GradeView(Grade, db.session))
admin.add_link(MyLogoutMenuLink(name='Logout', category='', icon_type='glyph', icon_value='glyphicon-off'))


with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template("register.html")

@app.route('/register', methods=['POST', 'GET'] )
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get('username')
    password = request.form.get('password')
    if not username and not password:
        return render_template("register.html", username_error="Username Required", password_error="Password Required")
    if not username:
        return render_template("register.html", username_error="Username Required")
    if not password:
        return render_template("register.html", password_error="Password Required")
    active = User.query.filter_by(username=username).first() is not None
    if active:
        return render_template("register.html", error="User Already Exist")
    hashed_password = bcrypt.generate_password_hash(password=password)
    new_user = User(username = username, password = hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return redirect(url_for("login"))

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get('username')
    password = request.form.get('password')
    if not username and not password:
        return render_template("login.html", username_error="Username Required", password_error="Password Required")
    if not username:
        return render_template("login.html", username_error="Username Required")
    if not password:
        return render_template("login.html", password_error="Password Required")
    user = User.query.filter_by(username=username).first()
    if not user or not bcrypt.check_password_hash(user.password, password):
        return render_template("login.html", error="Incorrect Password")
    login_user(user)
    if user.role == "Admin":
        return redirect(url_for("admin.index"))
    return redirect(url_for("home"))

@app.route("/grades/<course>", methods=["POST", "GET"])
@login_required
def grades(course):
    course = Course.query.filter_by(name=course).first()
    if request.method == "GET":
        return render_template("grades.html", course=course)
    name = request.form.get("name")
    value = request.form.get("grade")
    student = User.query.filter_by(username=name).first()
    grade = Grade.query.filter_by(course_id=course.id, student_id=student.id).first()
    grade.value = value
    db.session.commit()
    return render_template("grades.html", course=course)


@app.route("/createcourse", methods=["POST"])
@login_required
def add():
    name = request.form.get('name')
    time = request.form.get('time')
    capacity = request.form.get('capacity')
    course = Course(name = name, time = time, capacity = capacity)
    course.teachers.append(current_user)
    db.session.add(course)
    db.session.commit()
    return redirect(url_for("home"))


@app.route("/enroll", methods=["POST", "GET"])
@login_required
def enroll():
    course_name = request.form.get("name")
    course = Course.query.filter_by(name = course_name).first()
    if current_user.role == "Teacher":
        course.teachers.append(current_user)
    else:
        course.capacity -= 1
        course.students.append(current_user)
        grade = Grade(course_id=course.id, student_id=current_user.id, value=0.0)
        db.session.add(grade)
    db.session.commit()
    return redirect(url_for("catalog"))


@app.route("/unenroll/<name>/<course>", methods=["POST"])
@login_required
def unenroll_user(name, course):
    course = Course.query.filter_by(name = course).first()
    student = User.query.filter_by(username = name).first()
    print(student, course)
    if current_user.role == "Teacher":
        course.capacity += 1
        course.students.remove(student)
        grade = Grade.query.filter_by(course_id=course.id, student_id=student.id).first()
        db.session.delete(grade)
    db.session.commit()
    return redirect(url_for(f"grades", course = course.name))

@app.route("/unenroll", methods=["POST", "GET"])
@login_required
def unenroll():
    course_name = request.form.get("name")
    course = Course.query.filter_by(name = course_name, ).first()
    if current_user.role == "Teacher":
        db.session.delete(course)
    else:
        course.capacity += 1
        course.students.remove(current_user)
        grade = Grade.query.filter_by(course_id=course.id, student_id=current_user.id).first()
        #if grade line maybe fixes a bug for deletion of class may remove if not needed
        if grade:
            db.session.delete(grade)
    db.session.commit()
    return redirect(url_for("catalog"))

@app.route("/catalog")
@login_required
def catalog():
    courses = Course.query.all()
    enrolled = current_user.courses_enrolled
    if current_user.role == "Teacher":
        enrolled = current_user.courses_taught
    return render_template("catalog.html", courses=courses, enrolled=enrolled)

@app.route('/home')
@login_required
def home():
    courses = current_user.courses_enrolled
    if current_user.role == "Teacher":
        courses = current_user.courses_taught
    return render_template("home.html", courses = courses)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)

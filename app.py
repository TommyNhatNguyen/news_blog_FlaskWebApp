import pandas as pd 
import mysql.connector 
from flask import Flask, render_template, flash, url_for, get_flashed_messages, jsonify, json, redirect, request
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, FileField, DateField, SubmitField, PasswordField, BooleanField, ValidationError, TextAreaField
from wtforms.validators import DataRequired, EqualTo, Length
from wtforms.widgets import TextArea
from flask_wtf.file import FileField
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_required, login_user, current_user, logout_user
from flask_login import UserMixin
from flask_ckeditor import CKEditor, CKEditorField
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_mail import Mail
from flask_mail import Message
from time import time
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid as uuid
import os 


# Create A Flask App 
app = Flask(__name__)
# Add Configs
app.config['SECRET_KEY'] = 'password'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1234@localhost/users'
UPLOAD_FOLDER = 'static/users_profile/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CKEDITOR_PKG_TYPE'] = 'standard'
# Initialize the app with the extension 
db = SQLAlchemy(app)
migrate = Migrate(app, db)
admin = Admin(app)
# Add rich text editor
ckeditor = CKEditor(app)
# Flask login 
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Vui lòng đăng nhập để tiếp tục!"
login_manager.login_message_category = "warning"

# --------Forms---------
# Create Register Form
class RegisterForm(FlaskForm):
    username = StringField("Tên tài khoản", validators=[DataRequired()])
    email = EmailField("Email", validators=[DataRequired()])
    password = PasswordField('Mật Khẩu', validators=[DataRequired(),
                                                     EqualTo('password_confirm', message='Mật khẩu xác nhận không chính xác!')])
    password_confirm = PasswordField("Nhập lại mật khẩu", validators=[DataRequired()])
    submit = SubmitField("Xác nhận")

# Create Login Form
class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired()])
    password = PasswordField('Mật Khẩu', validators=[DataRequired()])
    submit = SubmitField("Đăng nhập")

# Create User Form
class UserForm(RegisterForm):
    about_author = TextAreaField("Giới thiệu")
    profile_pic = FileField("Ảnh đại diện")

# Create Post Form
class PostForm(FlaskForm):
    title = TextAreaField('Tiêu đề', validators=[DataRequired()])
    content = CKEditorField('Nội dung')
    tags = StringField('Thẻ Tag')
    submit = SubmitField('Đăng bài')

# Create EmptyForm
class EmptyForm(FlaskForm):
    submit = SubmitField('Submit')

# --------Database---------
# Create Users Database
followers = db.Table('followers', 
                     db.Column('follower_id', db.Integer, db.ForeignKey('users.id')),
                     db.Column('followed_id', db.Integer, db.ForeignKey('users.id'))
                     )

class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False, unique=True)
    password_hash = db.Column(db.String(200))
    about_author = db.Column(db.Text, nullable=True)
    profile_pic = db.Column(db.String(1000), nullable=True)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    posts = db.relationship('Posts', backref='users')
    followed = db.relationship('Users', secondary=followers,
                               primaryjoin=(followers.c.follower_id == id),
                               secondaryjoin=(followers.c.followed_id == id),
                               backref=db.backref('followers', lazy='dynamic'),
                               lazy='dynamic'
                               )
 
    @property
    def password(self):
        raise AttributeError('Password is not a readale attribute!')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)
    
    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)
    
    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0
    
    def followed_posts(self):
        followed = Posts.query.join(
            followers, (followers.c.followed_id == Posts.user_id)).filter(
                followers.c.follower_id == self.id)
        own = Posts.query.filter_by(user_id=self.id)
        return followed.union(own).order_by(Posts.timestamp.desc())
    
    # Create a string
    def __repr__(self):
        return '<Name %r>' % self.username
    
class Posts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=True)
    content = db.Column(db.Text, nullable=False)
    tags = db.Column(db.String(200), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text)	
    content	= db.Column(db.Text)
    link = db.Column(db.Text)
    author = db.Column(db.Text)
    date = db.Column(db.Text)
    image = db.Column(db.Text)


# Flask and Flask-SQLAlchemy initialization here
admin.add_view(ModelView(Users, db.session))
admin.add_view(ModelView(Posts, db.session))

# --------Read Data---------
vnexpress = pd.read_csv("data/vnexpress_clean.csv")

# --------Add Views---------
@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

@app.route('/follow/<int:id>', methods=['POST'])
@login_required
def follow(id):
    form = EmptyForm()
    if form.validate_on_submit():
        user = Users.query.filter_by(id=id).first()
        if user is None:
            flash('Người dùng {} không tồn tại!'.format(id))
            return redirect(url_for('index'))
        if user == current_user:
            flash("Bạn không thể tự theo dõi chính bạn!")
            return redirect(url_for('index'))
        current_user.follow(user)
        db.session.commit()
        flash("Bạn theo dõi {} thành công!".format(user.username))
        return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))

@app.route('/unfollow/<int:id>', methods=['POST'])
@login_required
def unfollow(id):
    form = EmptyForm()
    if form.validate_on_submit():
        user = Users.query.filter_by(id=id).first()
        if user is None:
            flash('Người dùng {} không tồn tại!'.format(id))
            return redirect(url_for('index'))
        if user == current_user:
            flash("Bạn không thể hủy theo dõi chính bạn!")
            return redirect(url_for('index'))
        current_user.unfollow(user)
        db.session.commit()
        flash("Bạn đã hủy theo dõi {} thành công!".format(user.username))
        return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))

@app.route('/')
@app.route('/index')
def index():
    return redirect(url_for('community'))
    # return render_template('index.html')

@app.route('/community')
def community():
    user = None
    news = News.query.order_by(News.title)
    posts = Posts.query.order_by(Posts.date_posted)
    follow_form = EmptyForm()
    if current_user.is_authenticated:
        id = current_user.id
        user = Users.query.get_or_404(id)
        return render_template('community.html', news=news, user=user, posts=posts, follow_form=follow_form)
    else:
        return render_template('community.html', news=news, user=user, posts=posts,  follow_form=follow_form)

@app.route('/community/community-post/<int:post_id>')
def community_post(post_id):
    post = Posts.query.get_or_404(post_id)
    return render_template('community_post.html', post_id=post_id, post=post)

@app.route('/add-post', methods=['GET', 'POST'])
@login_required
def add_post():
    form = PostForm()
    author_id = current_user.id
    number_of_posts = Posts.query.filter_by(author_id=author_id).count() 
    if form.validate_on_submit():
        title = form.title.data
        content = form.content.data
        tags = form.tags.data
        post = Posts(title=title, content=content, tags=tags, author_id=author_id)
        try:
            db.session.add(post)
            db.session.commit()
            flash("Đăng bài thành công!", 'message')
            return redirect(url_for('community'))
        except:
            flash("Đăng bài xảy ra lỗi, vui lòng thử lại!", 'error')
            return render_template('add_post.html', form=form, num_posts=number_of_posts)
    return render_template('add_post.html', form=form, num_posts=number_of_posts)

@app.route('/user-profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    form = UserForm()
    id = current_user.id 
    user_to_update = Users.query.get_or_404(id)
    if request.method == 'POST':
        user_to_update.username = request.form['username']
        user_to_update.about_author = request.form['about_author']
        # Get Image's name
        pic_filename = secure_filename(request.files['profile_pic'].filename)
        if (pic_filename) and (Users.query.get_or_404(id) is not None):
            user_to_update.profile_pic = request.files['profile_pic']
            # Grab Image Name
            pic_filename = secure_filename(user_to_update.profile_pic.filename)
            # Set UUID 
            pic_filename_new = str(uuid.uuid1()) + '_' + pic_filename
            user_to_update.profile_pic = pic_filename_new
            # Save image to static/users_profile
            saver = request.files['profile_pic']
            saver.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_filename_new))
        try:
            db.session.commit()
            flash("Cập nhật thành công!", 'message')
            return render_template('user_profile.html', form=form, user=user_to_update)
        except:
            flash("Lỗi cập nhật, vui lòng thử lại!", 'error')
            return render_template('user_profile.html', form=form, user=user_to_update)
    else:
        return render_template('user_profile.html', form=form, user=user_to_update)

@app.route('/news')
def news():
    # images = vnexpress['image']
    # title = vnexpress['title']
    # date = vnexpress['date']
    # link = vnexpress['link']
    news = News.query.order_by(News.title)
    return render_template('news.html', 
                        #    images=images,
                        #    title=title,
                        #    date=date,
                        #    link=link,
                           news=news)

@app.route('/news/new/<int:id>')
@login_required
def new(id):
    new = News.query.get_or_404(id)
    return render_template('new.html', id=id, new=new)

@app.route('/delete/<int:id>', methods=['GET', 'POST'])
def delete(id):
    form = RegisterForm()
    user_to_delete = Users.query.get_or_404(id)
    try: 
        db.session.delete(user_to_delete)
        db.session.commit()
        # Get current users
        current_users = Users.query.order_by(Users.date_added)
        flash(f"Email đã được xóa", 'message')
        return render_template('register.html', form=form, id=id, users=current_users)
    except:
        flash(f"Đã có lỗi xảy ra trong lúc xóa, vui lòng thử lại!", 'error')

@app.route('/register', methods=['POST', 'GET'])
def register():
    username=None
    email = None
    password = None
    password_confirm = None
    form = RegisterForm()
    if form.validate_on_submit():
        # Check if user exist
        user = Users.query.filter_by(email=form.email.data).first()
        if user is None:
            username = form.username.data
            email = form.email.data
            # Hash password
            password = form.password.data
            password_hash = generate_password_hash(password)
            # Add new user to database
            user = Users(username=username,
                         email=email,
                         password_hash=password_hash)
            db.session.add(user)
            db.session.commit()
            flash("Tài khoản tạo thành công!", 'message')
        else:
            flash(f"Email: {form.email.data} đã tồn tại!", 'error')
    # Clear the data
    form.username.data = ''
    form.email.data = ''
    form.password.data = ''
    form.password_confirm.data = ''
    # Get current users
    current_users = Users.query.order_by(Users.date_added)
    return render_template('register.html', form=form, users=current_users)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = Users.query.filter_by(email=form.email.data).first()
        # Check if user exist
        if user:
            # Check if password matched
            if check_password_hash(user.password_hash, form.password.data):
                login_user(user)
                flash("Đăng nhập thành công!", 'message')
                return redirect(url_for('community'))
            else:
                flash("Mật khẩu không đúng!", 'error')
        else:
            flash("Email không tồn tại!", 'error')
    return render_template('login.html', form=form)

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    flash("Đăng xuất thành công!")
    return redirect(url_for('login'))

if __name__ == "__main__":
    # with app.app_context():
    #     db.create_all()
    app.run(debug=True)

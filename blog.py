from flask import Flask,render_template,flash,redirect,url_for,session,logging,request,send_from_directory
from flask_mysqldb import MySQL
from wtforms import Form,StringField,TextAreaField,PasswordField,validators
from passlib.hash import sha256_crypt
from functools import wraps
import os
from werkzeug.utils import secure_filename
from random import randrange
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" in session:
            return f(*args, **kwargs)
        else:
            flash("Bu Sayfayı Görüntülemek İçin Lütfen Giriş Yapın...", "danger")
            return redirect(url_for("login"))
        
    return decorated_function

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class RegisterForm(Form):
    
    name = StringField("İsim Soyisim",validators=[validators.Length(min = 4, max = 25)])
    username = StringField("Kullanıcı Adı",validators=[validators.Length(min = 5, max = 35)])
    email = StringField("Email Adresi",validators=[validators.Email(message = "Lütfen Geçerli Bir Email Adresi Girin...")])
    password = PasswordField("Parola:",validators=[
        validators.DataRequired(message = "Lütfen Bir Parola Belirleyin..."),
        validators.EqualTo(fieldname = "confirm", message = "Parola Hatalı...")
    ])
    confirm = PasswordField("Parola Tekrar:")

class LoginForm(Form):
    
    username = StringField("Kullanıcı Adı")
    password = PasswordField("Parola")

class ArticleForm(Form):
    title = StringField("Makale Başlığı", validators = [validators.Length(min = 5, max = 100)])
    content = TextAreaField("Makale İçeriği", validators = [validators.Length(min = 10)])

class ChangePasswordForm(Form):
    old_password = PasswordField("Eski Parola")
    password = PasswordField("Yeni Parola:",validators=[
        validators.DataRequired(message = "Lütfen Bir Parola Belirleyin..."),
        validators.EqualTo(fieldname = "confirm", message = "Parola Hatalı...")
    ])
    confirm = PasswordField("Yeni Parola Tekrar:")

class ForgotPasswordUser(Form):
    username = StringField("Kullanıcı Adı")

class ConfirmPasswordForm(Form):
    kod = StringField("KOD")

class NewPassword(Form):
    password = PasswordField("Parola:",validators=[
        validators.DataRequired(message = "Lütfen Bir Parola Belirleyin..."),
        validators.EqualTo(fieldname = "confirm", message = "Parola Hatalı...")
    ])
    confirm = PasswordField("Parola Tekrar:") 

UPLOAD_FOLDER = 'path/to/the/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app = Flask(__name__)
app.secret_key = "random_key"

app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""
app.config["MYSQL_DB"] = "database"
app.config["MYSQL_CURSORCLASS"] = "DictCursor"

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

mysql = MySQL(app)

@app.route("/")
def layout():
    return render_template("layout.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/dashboard")
@login_required
def dashboard():

    cursor = mysql.connection.cursor()

    sorgu = "select * from articles where author = %s"

    result = cursor.execute(sorgu,(session["username"],))

    if result > 0:
        articles = cursor.fetchall()
        return render_template("dashboard.html", articles = articles)
    else:
        return render_template("dashboard.html")

@app.route("/delete/<string:id>")
@login_required
def delete(id):
    
    cursor = mysql.connection.cursor()

    sorgu = "select * from articles where author = %s and id = %s"

    result = cursor.execute(sorgu,(session["username"],id))

    if result > 0:
        sorgu2 = "delete from articles where id = %s"

        cursor.execute(sorgu2,(id,))

        mysql.connection.commit()

        flash("Makale başarıyla silindi...", "success")

        return redirect(url_for("dashboard"))

    else:
        flash("Böyle bir makale yok veya böyle bir işleme yetkiniz yok...", "danger")

        return redirect(url_for("dashboard"))

@app.route("/edit/<string:id>", methods = ["GET", "POST"])
@login_required
def update(id):
    
    if request.method == "GET":
        cursor = mysql.connection.cursor()

        sorgu = "select * from articles where id = %s and author = %s"

        result = cursor.execute(sorgu,(id,session["username"]))

        if result == 0:
            flash("Böyle bir makale yok veya böyle bir işleme yetkiniz yok...", "danger")
            return redirect(url_for("layout"))
        else:
            article = cursor.fetchone()
            form = ArticleForm()

            form.title.data = article["title"]
            form.content.data = article["content"]

            return render_template("update.html", form = form)
            
    else:
        form = ArticleForm(request.form)

        newTitle = form.title.data
        newContent = form.content.data

        sorgu2 = "update articles set title = %s, content = %s where id = %s"

        cursor = mysql.connection.cursor()

        cursor.execute(sorgu2,(newTitle,newContent,id))

        mysql.connection.commit()

        cursor.close()

        flash("Makale başarıyla güncellendi...")

        return redirect(url_for("dashboard"))
    
@app.route("/register", methods = ["GET", "POST"])
def register():
    form = RegisterForm(request.form)

    cursor = mysql.connection.cursor()

    sorgu2 = "select * from users where username = %s"

    result = cursor.execute(sorgu2,(form.username.data,))

    if request.method == "POST" and form.validate() and not(result):
        
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(form.password.data)

        cursor = mysql.connection.cursor()
        
        sorgu = "Insert into users(name,email,username,password) VALUES(%s,%s,%s,%s)"

        cursor.execute(sorgu,(name,email,username,password))

        mysql.connection.commit()

        cursor.close()

        flash("Kayıt İşleminiz Başarıyla Gerçekleştirildi...", "success")

        return redirect(url_for("login"))

    else:
        return render_template("register.html", form = form)

@app.route("/login", methods = ["GET", "POST"])
def login():
    form = LoginForm(request.form)

    if request.method == "POST":
    
        username = form.username.data
        password_entered = form.password.data

        cursor = mysql.connection.cursor()

        sorgu = "select * from users where username = %s"

        result = cursor.execute(sorgu,(username,))

        if result > 0:
            data = cursor.fetchone()
            real_password = data["password"]
            
            if sha256_crypt.verify(password_entered,real_password):
                flash("Başarıyla giriş yapıldı...", "success")

                session["logged_in"] = True
                session["username"] = username

                return redirect(url_for("layout"))

            else:
                flash("Parola Hatalı...", "danger")
                return redirect(url_for("login"))

        else:
            flash("Kullanıcı Adı veya Parola hatalı...", "danger")
            return redirect(url_for("login"))

    return render_template("login.html", form = form)

@app.route("/forgotpassworduser", methods = ["GET", "POST"])
def forgot_password_user():
    form = ForgotPasswordUser(request.form)
    
    
    if request.method == "POST":
        username = request.form.get("keyword2")
        cursor = mysql.connection.cursor()

        sorgu = "select * from users where username = %s"

        result = cursor.execute(sorgu,(username,))

        if result:
            flash("Lütfen " + username + " adlı kullanıcının e-mail adresine gönderilen kodu giriniz.", "success")
            return redirect(url_for("forgot_password"))

        else:
            flash("Böyle bir kullanıcı yok...", "danger")
            return redirect(url_for("forgot_password_user"))

    else:
        return render_template("forgotpassworduser.html", form = form)

@app.route("/forgotpassword", methods = ["GET", "POST"])
def forgot_password():
    form2 = ConfirmPasswordForm(request.form)

    kullanici = request.form.get("keyword2")

    

    print(kullanici)

    cursor = mysql.connection.cursor()

    sorgu = "select * from users where username = %s"

    result = cursor.execute(sorgu,(kullanici,))

    
    return render_template("forgotpassword.html", form = form2)

    if request.method == "POST":
        if True:
            
            
            kod = randrange(100000, 1000000)
            
            cursor = mysql.connection.cursor()

            sorgu2 = "select * from users where username = %s"

            cursor.execute(sorgu2,(kullanici,))

            data = cursor.fetchone()
            email = data["email"]

            cursor.close()

            try:    
                message = MIMEMultipart()  

                message["From"] =  "erenkarakaya93@hotmail.com"

                message["To"] = email 

                message["Subject"] = "Şifre Değiştirme"  

        
                body = "Şifre Değiştirme Kodunuz:" + str(kod)


                message_body =  MIMEText(body,"plain")  

                message.attach(message_body) 

            
                mail = smtplib.SMTP("smtp.gmail.com",587)  

                mail.ehlo() 
 
                mail.starttls() 

                mail.login("erenkarakaya93@gmail.com","sprinkai96101") 

                mail.sendmail(message["From"],message["To"],message.as_string())  
                
                mail.close()

                if form2.kod.data == str(kod):
                    flash("Lütfen yeni şifrenizi belirleyin", "success") 
                    return render_template("newpassword.html")
                else:
                    flash("Kod yanlış...", "danger")
                    return redirect(url_for("forgot_password_user"))

            except:
                flash("Mail gönderilirken hata oluştu...", "danger") 
                return render_template("forgotpassworduser.html")

        else:
            flash("Böyle bir kullanıcı yok...", "danger")
            return redirect(url_for("forgot_password_user"))        
    
    
    
    
@app.route("/newpassword/<username>")
def new_password(username):
    form = NewPassword(request.form)

    if request.method == "POST" and form.validate():

        new_password = sha256_crypt.encrypt(form.password.data)
        
        cursor = mysql.connection.cursor()
        
        sorgu = "update users set password = %s where username = %s"

        cursor.execute(sorgu,(new_password, username))

        mysql.connection.commit()

        cursor.close()

    else:
        return render_template("newpassword.html", form = form)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def upload_file():
    if request.method == 'POST':
        
        if 'file' not in request.files:
            flash('Böyle bir dosya yok...', "danger")
            return redirect(request.url)
        file = request.files['file']

        if file.filename == '':
            flash('Dosya seçilmedi...', "danger")
            return redirect(request.url)

        if file and allowed_file(file.filename):
            file.filename = session["username"]+".jpg"
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            flash("Profil fotoğrafı güncellendi...", "success")
            return redirect(url_for('uploaded_file', filename=filename))
                                                                        
    else:
        return render_template("settings.html")

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)

@app.route("/changepassword", methods = ["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm(request.form)

    if request.method == "POST":
        old_password = form.old_password.data
        new_password = sha256_crypt.encrypt(form.password.data)

        cursor = mysql.connection.cursor()

        sorgu = "select * from users where username = %s"

        cursor.execute(sorgu,(session["username"],))

        data = cursor.fetchone()
        real_password = data["password"]

        if sha256_crypt.verify(old_password,real_password) and form.validate():

            cursor = mysql.connection.cursor()

            sorgu2 = "update users set password = %s where username = %s"

            cursor.execute(sorgu2,(new_password,session["username"]))

            mysql.connection.commit()

            cursor.close()

            flash("Parolanız başarıyla değiştirildi...", "success")

            return redirect(url_for("layout"))
        
        else:
            flash("Parola Hatalı...", "danger")
            return redirect(url_for("change_password"))

    else:
        return render_template("changepassword.html", form = form)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("layout"))

@app.route("/articles")
def articles():
    cursor = mysql.connection.cursor()

    sorgu = "select * from articles"

    result = cursor.execute(sorgu)

    if result > 0:
        articles = cursor.fetchall()
        return render_template("articles.html", articles = articles)
    else:
        return render_template("articles.html")
    
@app.route("/addarticle", methods = ["GET", "POST"])
@login_required
def addArticle():
    form = ArticleForm(request.form)
    if request.method == "POST" and form.validate():
        title = form.title.data
        content = form.content.data

        cursor = mysql.connection.cursor()

        sorgu = "insert into articles(title,author,content) values(%s,%s,%s)"

        cursor.execute(sorgu,(title,session["username"],content))

        mysql.connection.commit()

        cursor.close()

        flash("Makale Başarıyla Eklendi...", "success")

        return redirect(url_for("dashboard"))

    return render_template("addarticle.html", form = form)

@app.route("/article/<string:id>")
def article(id):
    cursor = mysql.connection.cursor()

    sorgu = "select * from articles where id = %s"

    result = cursor.execute(sorgu,(id,))

    if result > 0:
        article = cursor.fetchone()
        return render_template("article.html",article = article)
    else:
        return render_template("article.html")

@app.route("/search", methods = ["GET", "POST"])
def search():
    if request.method == "GET":
        return redirect(url_for("layout"))
    else:
        keyword = request.form.get("keyword")

        cursor = mysql.connection.cursor()

        sorgu = "select * from articles where title like '%" + keyword + "%'"

        result = cursor.execute(sorgu)

        if result == 0:
            flash("Aranan kelimeye uygun makale bulunamadı...", "warning")
            return redirect(url_for("articles"))

        else:
            articles = cursor.fetchall()

            return render_template("articles.html", articles = articles)

if __name__ == "__main__":
    app.run(debug=True)
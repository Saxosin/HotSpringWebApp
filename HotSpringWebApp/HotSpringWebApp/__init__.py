from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dev'

    from . import views
    app.register_blueprint(views.bp)

    return app

# 👉 Expose `app` here for Gunicorn
app = create_app()

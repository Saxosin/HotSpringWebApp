from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dev'

    from . import views
    app.register_blueprint(views.bp)

    return app

# 🔥 Add this line so Gunicorn can find it
app = create_app()

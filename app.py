from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from slugify import slugify

app = Flask(__name__) 
app.jinja_env.globals.update(slugify=slugify)

import controllers.config

import models.dbmodel


import controllers.routes


if __name__=='__main__':
    app.run(debug=True)




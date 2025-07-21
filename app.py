from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__) 

import controllers.config

import models.dbmodel


import controllers.routes


if __name__=='__main__':
    app.run(debug=True)




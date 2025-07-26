from flask import Flask
from slugify import slugify

app = Flask(__name__) 
app.jinja_env.globals.update(slugify=slugify)            #make slugify available to all jinja templates


import controllers.config

import models.dbmodel

import controllers.routes


if __name__=='__main__':
    app.run()




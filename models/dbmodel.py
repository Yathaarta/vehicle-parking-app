from app import app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint

db = SQLAlchemy(app)



class User(db.Model):
    __tablename__ = 'user'

    user_id = db.Column(db.Integer, primary_key=True, unique=True, autoincrement=True)
    email_id = db.Column(db.String(50), unique=True, nullable=False)
    pass_wd = db.Column(db.String(100), nullable=False)
    user_name = db.Column(db.String(50), nullable=False)

    bookings = db.relationship('UserBookings', backref='user', cascade="all, delete-orphan", passive_deletes=True)
    history = db.relationship('UserHistory', backref='user', cascade="all, delete-orphan", passive_deletes=True)


class UserBookings(db.Model):
    __tablename__ = 'user_bookings'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, unique=True, nullable=False)
    user_id = db.Column(db.String(8), db.ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey("parking_spot.spot_id", ondelete="SET NULL"), nullable=True)
    parking_time = db.Column(db.DateTime, nullable=False)
    leaving_time = db.Column(db.DateTime, nullable=False)
    parking_cost = db.Column(db.Numeric(7, 2), nullable=False)
    vehicle_no = db.Column(db.String(12), nullable=False)


class UserHistory(db.Model):
    __tablename__ = 'booking_history'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, unique=True, nullable=False)
    user_id = db.Column(db.String(8), db.ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey("parking_spot.spot_id", ondelete="SET NULL"), nullable=True)
    booking_time = db.Column(db.DateTime, nullable=False)
    leaving_time = db.Column(db.DateTime, nullable=False)
    parking_cost = db.Column(db.Numeric(7, 2), nullable=False)
    vehicle_no = db.Column(db.String(12), nullable=False)


class ParkingLot(db.Model):
    __tablename__ = 'parkinglot'

    lot_id = db.Column(db.String(8), primary_key=True, unique=True, nullable=False)
    area_type = db.Column(db.String(20), nullable=False)
    city = db.Column(db.String(15), nullable=True)
    tourist_place = db.Column(db.String(20), nullable=True)
    primelocation_name = db.Column(db.String(20), nullable=False)
    price_per_hr = db.Column(db.Numeric(5, 2), nullable=False)
    address = db.Column(db.String(150), unique=True, nullable=False)
    pincode = db.Column(db.Numeric(6), nullable=False)
    max_spots = db.Column(db.Numeric(4), nullable=False)

    spots = db.relationship('ParkingSpot', backref='lot', cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("area_type IN ('city','tourist place','both')", name='check_area_type'),
    )


class ParkingSpot(db.Model):
    __tablename__ = 'parking_spot'

    spot_id = db.Column(db.Integer, primary_key=True, autoincrement=True, unique=True, nullable=False)
    lot_id = db.Column(db.String(8), db.ForeignKey("parkinglot.lot_id", ondelete="CASCADE"), nullable=False)
    status = db.Column(db.String(1), nullable=False)

    bookings = db.relationship('UserBookings', backref='spot', passive_deletes=True)
    history = db.relationship('UserHistory', backref='spot', passive_deletes=True)

    __table_args__ = (
        CheckConstraint("status IN ('O','A')", name='check_status_occupied'),
    )


with app.app_context():
    db.create_all()


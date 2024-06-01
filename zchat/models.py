import json

from flask import current_app, url_for

from zchat.db import db
from zchat.rand import *

class User(db.Model):
    __tablename__ = 'USER'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    phone_number = db.Column(db.String, nullable=False, default='13800001111')

    avatar_name = db.Column(db.String, nullable=False, default='default.jpg')
    nickname = db.Column(db.String, nullable=False, default='专家785') # TODO use random name
    signature_text = db.Column(db.String, nullable=False, default='Hello World!')

    gender = db.Column(db.String, nullable=False, default='未知')
    edubg = db.Column(db.String, nullable=False, default='未知')
    yearofwork = db.Column(db.String, nullable=False, default='未知')

    as_expert = db.Column(db.Integer, nullable=False, default=0)
    as_newbie = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.Index('index_USER_phone_number', 'phone_number', unique=True),

        db.Index('index_USER_name', 'nickname', unique=False),
        db.Index('index_USER_signature_text', 'signature_text', unique=False),

        db.Index('index_USER_gender', 'gender', unique=False),
        db.Index('index_USER_edubg', 'edubg', unique=False),
        db.Index('index_USER_yearofwork', 'yearofwork', unique=False),

        db.Index('index_USER_as_expert', 'as_expert', unique=False),
        db.Index('index_USER_as_newbie', 'as_newbie', unique=False),
    )

    def to_dict(self):
        return {
            'id' : self.id,
            'phone_number' : self.phone_number,

            'avatar': url_for('static', filename=f'images/{self.avatar_name}'),
            'nickname' : self.nickname,
            'signature_text': self.signature_text,

            'gender' : self.gender,
            'edubg' : self.edubg,
            'yearofwork' : self.yearofwork,

            'as_expert': self.as_expert,
            'as_newbie': self.as_newbie,
        }

class UserOps:
    def __init__(self, session):
        self.session = session

    def get_or_create_user(self, phone_number)->int:
        current_app.logger.debug(f"get_or_create_user, {phone_number}")
        try:
            user = self.session.query(User).filter_by(phone_number=phone_number).first()
            if user:
                return user.id

            # TODO with better random name
            user = User(phone_number=phone_number, nickname=random_name())
            self.session.add(user)
            self.session.commit()
            current_app.logger.debug(f"added user, id: {user.id}, phone_number: {phone_number}")
            return user.id
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to add user {phone_number}, error {str(e)}")
        return None

    def update_avatar(self, id, avatar_name)->bool:
        current_app.logger.debug(f"update_avatar, {id}, {avatar_name}")
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.avatar_name = avatar_name

                self.session.commit()
                current_app.logger.debug(f"updated user avatar {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user avatar {id}, error {str(e)}")
        return False

    def update_nickname(self, id, nickname)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.nickname = nickname

                self.session.commit()
                current_app.logger.debug(f"updated user nickname {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user nickname {id}, error {str(e)}")
        return False

    def update_gender(self, id, gender)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.gender = gender

                self.session.commit()
                current_app.logger.debug(f"updated user gender {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user gender {id}, error {str(e)}")
        return False

    def update_edubg(self, id, edubg)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.edubg = edubg

                self.session.commit()
                current_app.logger.debug(f"updated user edubg {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user edubg {id}, error {str(e)}")
        return False

    def update_yearofwork(self, id, yearofwork)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.yearofwork = yearofwork

                self.session.commit()
                current_app.logger.debug(f"updated user yearofwork {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user yearofwork {id}, error {str(e)}")
        return False

    def update_signature(self, id, signature)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.signature_text = signature

                self.session.commit()
                current_app.logger.debug(f"updated user signature {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user signature {id}, error {str(e)}")
        return False

    def update_info(self, id, phone_number, nickname, gender, edubg, yearofwork, signature_text)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.phone_number = phone_number

                user.nickname = nickname
                user.signature_text = signature_text

                user.gender = gender
                user.edubg = edubg
                user.yearofwork = yearofwork

                self.session.commit()
                current_app.logger.debug(f"updated user {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user {id}, error {str(e)}")
        return False

    def get_one(self, id)->User:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            return user
        except Exception as e:
            current_app.logger.debug(f'failed to get user, error {str(e)}')
            return None

    def get_all(self)->list:
        try:
            users = self.session.query(User).all()
            current_app.logger.debug(f'len of all users {len(users)}')
            return [user.to_dict() for user in users]
        except Exception as e:
            current_app.logger.debug(f'failed to get all users, error {str(e)}')
            return []

class Expert(db.Model):
    __tablename__ = 'EXPERT'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)

    email = db.Column(db.String, nullable=False, default='foo@bar.com')
    email_verified = db.Column(db.Integer, nullable=False, default=0)

    company = db.Column(db.String, nullable=False, default='')
    title = db.Column(db.String, nullable=False, default='')
    profession = db.Column(db.String, nullable=False, default='')
    business = db.Column(db.String, nullable=False, default='')
    price = db.Column(db.REAL, nullable=False, default=500.0)

    __table_args__ = (
        db.Index('index_EXPERT_email', 'email', unique=False),
        db.Index('index_EXPERT_email_verified', 'email_verified', unique=False),

        db.Index('index_EXPERT_company', 'company', unique=False),
        db.Index('index_EXPERT_title', 'title', unique=False),
        db.Index('index_EXPERT_profession', 'profession', unique=False),
        db.Index('index_EXPERT_business', 'business', unique=False),
        db.Index('index_EXPERT_price', 'price', unique=False),
    )

    def to_dict(self):
        return {
            'user_id' : self.user_id,

            'email' : self.email,
            'email_verified': self.email_verified,

            'company' : self.company,
            'title' : self.title,
            'profession': self.profession,
            'business': self.business,
            'price': self.price,
        }

class ExpertOps:
    def __init__(self, session):
        self.session = session

    def register_or_update(self, user_id, email, company, title, profession, business, price)->bool:
        current_app.logger.debug(f"register expert, {user_id}")
        try:
            user = self.session.query(User).filter_by(id=user_id).first()
            if user:
                user.as_expert = 1
            else:
                raise Exception(f'user does not exist, id: {user_id}')

            expert = self.session.query(Expert).filter_by(user_id=user_id).first()
            if expert:
                expert.email = email

                expert.company = company
                expert.title = title
                expert.profession = profession
                expert.business = business
                expert.price = price

                self.session.commit()
                current_app.logger.debug(f"updated expert {user_id}")
                return True
            else:
                expert = Expert(
                    user_id=user_id,
                    email=email,

                    company=company,
                    title=title,
                    profession=profession,
                    business=business,
                    price=price,
                )
                self.session.add(expert)
                self.session.commit()
                current_app.logger.debug(f"added expert, user_id: {user_id}")
                return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to add or update expert {user_id}, error {str(e)}")
        return False

    def get_one(self, user_id)->Expert:
        try:
            expert = self.session.query(Expert).filter_by(user_id=user_id).first()
            return expert
        except Exception as e:
            current_app.logger.debug(f'failed to get expert, error {str(e)}')
            return None

    def get_all(self)->list:
        try:
            experts = self.session.query(Expert).all()
            current_app.logger.debug(f'len of all experts {len(experts)}')
            return [expert.to_dict() for expert in experts]
        except Exception as e:
            current_app.logger.debug(f'failed to get all experts, error {str(e)}')
            return []

class Newbie(db.Model):
    __tablename__ = 'NEWBIE'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)

    target_company = db.Column(db.String, nullable=False, default="")
    target_title = db.Column(db.String, nullable=False, default="")
    target_profession = db.Column(db.String, nullable=False, default="")
    target_business = db.Column(db.String, nullable=False, default="")
    target_jd = db.Column(db.String, nullable=False, default="")

    __table_args__ = (
        db.Index('index_NEWBIE_target_company', 'target_company', unique=False),
        db.Index('index_NEWBIE_target_title', 'target_title', unique=False),
        db.Index('index_NEWBIE_target_profession', 'target_profession', unique=False),
        db.Index('index_NEWBIE_target_business', 'target_business', unique=False),
        db.Index('index_NEWBIE_target_jd', 'target_jd', unique=False),
    )

    def to_dict(self):
        return {
            'user_id' : self.user_id,
            'target_company' : self.target_company,
            'target_title' : self.target_title,
            'target_profession': self.target_profession,
            'target_business': self.target_business,
            'target_jd': self.target_jd,
        }

class NewbieOps:
    def __init__(self, session):
        self.session = session

    def register_or_update(self, user_id, company, title, profession, business, jd)->bool:
        current_app.logger.debug(f"register newbie, {user_id}")
        try:
            user = self.session.query(User).filter_by(id=user_id).first()
            if user:
                user.as_newbie = 1
            else:
                raise Exception(f'user does not exist, id: {user_id}')

            newbie = self.session.query(Newbie).filter_by(user_id=user_id).first()
            if newbie:
                newbie.target_company = company
                newbie.target_title = title
                newbie.target_profession = profession
                newbie.target_business = business
                newbie.target_jd = jd

                self.session.commit()
                current_app.logger.debug(f"updated newbie {user_id}")
                return True
            else:
                newbie = Newbie(
                    user_id=user_id,
                    target_company=company,
                    target_title=title,
                    target_profession=profession,
                    target_business=business,
                    target_jd=jd,
                )
                self.session.add(newbie)
                self.session.commit()
                current_app.logger.debug(f"added newbie, user_id: {user_id}")
                return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to add or update newbie {user_id}, error {str(e)}")
        return False

    def get_one(self, user_id)->Expert:
        try:
            newbie = self.session.query(Newbie).filter_by(user_id=user_id).first()
            return expert
        except Exception as e:
            current_app.logger.debug(f'failed to get newbie, error {str(e)}')
            return None

    def get_all(self)->list:
        try:
            newbies = self.session.query(Newbie).all()
            current_app.logger.debug(f'len of all newbies {len(newbies)}')
            return [newbie.to_dict() for newbie in newbies]
        except Exception as e:
            current_app.logger.debug(f'failed to get all newbies, error {str(e)}')
            return []

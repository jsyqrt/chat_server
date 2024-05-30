import json

from flask import current_app, url_for

from zchat.db import db

class User(db.Model):
    __tablename__ = 'USER'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    avatar_name = db.Column(db.String, nullable=True)
    phone_number = db.Column(db.String, nullable=False)
    nickname = db.Column(db.String, nullable=True)
    gender = db.Column(db.String, nullable=True)
    edubg = db.Column(db.String, nullable=True)
    yearofwork = db.Column(db.String, nullable=True)
    signature_text = db.Column(db.String)

    as_expert = db.Column(db.Integer, nullable=True)

    as_newbie = db.Column(db.Integer, nullable=True)
    target_company = db.Column(db.String, nullable=True)
    target_title = db.Column(db.String, nullable=True)
    target_profession = db.Column(db.String, nullable=True)
    target_business = db.Column(db.String, nullable=True)
    target_jd = db.Column(db.String, nullable=True)

    __table_args__ = (
        db.Index('index_USER_phone_number', 'phone_number', unique=True),
        db.Index('index_USER_name', 'nickname', unique=False),
        db.Index('index_USER_gender', 'gender', unique=False),
        db.Index('index_USER_edubg', 'edubg', unique=False),
        db.Index('index_USER_yearofwork', 'yearofwork', unique=False),
        db.Index('index_USER_signature_text', 'signature_text', unique=False),

        db.Index('index_USER_as_expert', 'as_expert', unique=False),

        db.Index('index_USER_as_newbie', 'as_newbie', unique=False),
        db.Index('index_USER_target_company', 'target_company', unique=False),
        db.Index('index_USER_target_title', 'target_title', unique=False),
        db.Index('index_USER_target_profession', 'target_profession', unique=False),
        db.Index('index_USER_target_business', 'target_business', unique=False),
        db.Index('index_USER_target_jd', 'target_jd', unique=False),
    )

    def to_dict(self):
        return {
            'id' : self.id,
            'avatar': url_for('static', filename=f'images/{self.avatar_name}'),
            'phone_number' : self.phone_number,
            'nickname' : self.nickname,
            'gender' : self.gender,
            'edubg' : self.edubg,
            'yearofwork' : self.yearofwork,
            'signature_text': self.signature_text,
            'as_expert': self.as_expert,

            'as_newbie': self.as_newbie,
            'target_company': self.target_company,
            'target_title' : self.target_title,
            'target_profession': self.target_profession,
            'target_business' : self.target_business,
            'target_jd' : self.target_jd,
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

            user = User(phone_number=phone_number)
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
                user.gender = gender
                user.edubg = edubg
                user.yearofwork = yearofwork
                user.signature_text = signature_text

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

    email = db.Column(db.String, nullable=True)
    email_verified = db.Column(db.Integer, nullable=True)

    company = db.Column(db.String, nullable=True)
    title = db.Column(db.String, nullable=True)
    profession = db.Column(db.String, nullable=True)
    business = db.Column(db.String, nullable=True)

    __table_args__ = (
        db.Index('index_EXPERT_email', 'email', unique=False),
        db.Index('index_EXPERT_email_verified', 'email_verified', unique=False),
        db.Index('index_EXPERT_company', 'company', unique=False),
        db.Index('index_EXPERT_title', 'title', unique=False),
        db.Index('index_EXPERT_profession', 'profession', unique=False),
        db.Index('index_EXPERT_business', 'business', unique=False),
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
        }

class ExpertOps:
    def __init__(self, session):
        self.session = session

    def register_or_update(self, user_id, email, company, title, profession, business)->bool:
        current_app.logger.debug(f"register, {user_id}")
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

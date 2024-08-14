import json
import uuid
import time
from enum import Enum

from flask import current_app, url_for

from zchat.db import db
from zchat.rand import *
from zchat.meili import add_expert_to_meili, update_expert_to_meili, add_newbie_to_meili, update_newbie_to_meili

PLATFORM_DISCOUNT = 0.8
SYSTEM_ACCOUNT = 0

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

    as_expert = db.Column(db.Integer, nullable=False, default=0) # 0 for false, 1 for true
    as_newbie = db.Column(db.Integer, nullable=False, default=0) # 0 for false, 1 for true

    current_as_expert = db.Column(db.Integer, nullable=False, default=0) # 0 for newbie, 1 for expert

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

            'current_as_expert': self.current_as_expert,
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

    def update_role(self, id, current_as_expert)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.current_as_expert = current_as_expert

                self.session.commit()
                current_app.logger.debug(f"updated user role {id}")
                return True
            else:
                current_app.logger.warn(f"no user {id}")
        except Exception as e:
            self.session.rollback()
            current_app.logger.warn(f"failed to update user role {id}, error {str(e)}")
        return False

    def update_info(self, id, phone_number, nickname, gender, edubg, yearofwork, signature_text, current_as_expert)->bool:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            if user:
                user.phone_number = phone_number

                user.nickname = nickname
                user.signature_text = signature_text

                user.gender = gender
                user.edubg = edubg
                user.yearofwork = yearofwork

                user.current_as_expert = current_as_expert

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

class AdminUser(db.Model):
    __tablename__ = 'ADMIN_USER'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)

    def to_dict(self):
        return {
            'id' : self.id,
            'user_id' : self.user_id,
        }

class AdminUserOps:
    def __init__(self, session):
        self.session = session

    def add_as_admin(self, user_id)->int:
        current_app.logger.debug(f"add_as_admin, {user_id}")
        try:
            admin_user = AdminUser(user_id=user_id)
            self.session.add(admin_user)
            self.session.commit()
            current_app.logger.debug(f"added admin user, id: {user_id}")
            return user_id
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to add admin user {user_id}, error {str(e)}")
        return None

    def is_admin(self, user_id)->bool:
        try:
            user = self.session.query(AdminUser).filter_by(user_id=user_id).first()
            return user is not None
        except Exception as e:
            current_app.logger.debug(f'failed to get admin, error {str(e)}')
            return False

    def get_all(self)->list:
        try:
            users = self.session.query(AdminUser).all()
            current_app.logger.debug(f'len of all admin users {len(users)}')
            return [user.to_dict() for user in users]
        except Exception as e:
            current_app.logger.debug(f'failed to get all admin users, error {str(e)}')
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

    services = db.Column(db.String, nullable=False, default='["模拟面试", "职业规划建议"]')

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

            'services': self.services,
        }

class ExpertOps:
    def __init__(self, session):
        self.session = session

    def register_or_update(self, user_id, email, company, title, profession, business, price, services)->bool:
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
                if services:
                    expert.services = services

                self.session.commit()
                current_app.logger.debug(f"updated expert {user_id}")
                update_to_meili = update_expert_to_meili(current_app, expert)
                current_app.logger.debug(f"update expert to meili result {update_to_meili }")
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

                if services:
                    expert.services = services

                self.session.add(expert)
                self.session.commit()
                current_app.logger.debug(f"added expert, user_id: {user_id}")
                add_to_meili = add_expert_to_meili(current_app, expert)
                current_app.logger.debug(f"add expert to meili result {add_to_meili}")
                return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to add or update expert {user_id}, error {str(e)}")
        return False

    def update_services(self, user_id, services)->bool:
        current_app.logger.debug(f"update expert services, {user_id}")
        try:
            user = self.session.query(User).filter_by(id=user_id).first()
            if user:
                user.as_expert = 1
            else:
                raise Exception(f'user does not exist, id: {user_id}')

            expert = self.session.query(Expert).filter_by(user_id=user_id).first()
            if expert:
                expert.services = services

                self.session.commit()
                current_app.logger.debug(f"updated expert {user_id}")
                add_to_meili = update_expert_to_meili(current_app, expert)
                current_app.logger.debug(f"add expert to meili result {add_to_meili}")
                return True
            else:
                current_app.logger.warn(f"expert does not exist, user_id: {user_id}")
                return False
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to update expert {user_id}, error {str(e)}")
        return False

    def get_one(self, user_id)->Expert:
        try:
            # TODO use join to return more info(i.e. User, Comment info)
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

                update_to_meili = update_newbie_to_meili(current_app, newbie)
                current_app.logger.debug(f"update newbie to meili result {update_to_meili}")
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

                add_to_meili = add_newbie_to_meili(current_app, newbie)
                current_app.logger.debug(f"add newbie to meili result {add_to_meili}")
                return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to add or update newbie {user_id}, error {str(e)}")
        return False

    def get_one(self, user_id)->Newbie:
        try:
            newbie = self.session.query(Newbie).filter_by(user_id=user_id).first()
            return newbie
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

class ChatWith(db.Model):
    __tablename__ = 'CHATWITH'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    receiver = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)

    __table_args__ = (
        db.Index('index_CHATWITH_sender', 'sender', unique=False),
        db.Index('index_CHATWITH_receiver', 'receiver', unique=False),
    )

    def to_dict(self):
        return {
            'sender' : self.sender,
            'receiver' : self.receiver,
        }

class ChatWithOps:
    def __init__(self, session):
        self.session = session

    def upsert_pair(self, sender, receiver)->bool:
        current_app.logger.debug(f"upsert_pair, {sender}, {receiver}")
        try:
            all = self.session.query(
                ChatWith,
            ).filter(
                ChatWith.sender==sender,
                ChatWith.receiver==receiver,
            ).all()

            if len(all) >= 1:
                current_app.logger.debug(f"chat_pair already exists")
                return True

            chat_pair = ChatWith(
                sender=sender,
                receiver=receiver,
            )
            self.session.add(chat_pair)
            self.session.commit()
            current_app.logger.debug(f"added chat pair")
            return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to upsert chat pair, error {str(e)}")
        return False

    def get_chatlist(self, self_id)->list:
        # Return list of ids
        try:
            chat_pairs = self.session.query(ChatWith).filter(
                db.or_(ChatWith.sender == self_id, ChatWith.receiver == self_id),
            ).all()
            current_app.logger.debug(f'len of all chat_pairs {len(chat_pairs)}')
            result = set()
            for chat_pair in chat_pairs:
                if chat_pair.sender == self_id:
                    result.add(chat_pair.receiver)
                else:
                    result.add(chat_pair.sender)
            return list(result)
        except Exception as e:
            current_app.logger.debug(f'failed to get chat_pairs, error {str(e)}')
            return []

class ChatMsg(db.Model):
    __tablename__ = 'CHATMSG'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    receiver = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    msg = db.Column(db.String, nullable=False, default='')
    msg_type = db.Column(db.Integer, nullable=False, default=0) # 0 is basic msg,
    timestamp = db.Column(db.REAL, nullable=False)

    __table_args__ = (
        db.Index('index_CHATMSG_sender', 'sender', unique=False),
        db.Index('index_CHATMSG_receiver', 'receiver', unique=False),
        db.Index('index_CHATMSG_timestamp', 'timestamp', unique=False),
    )

    def to_dict(self):
        return {
            'sender' : self.sender,
            'receiver' : self.receiver,
            'msg' : self.msg,
            'msg_type': self.msg_type,
            'timestamp' : self.timestamp,
        }

class ChatMsgOps:
    def __init__(self, session):
        self.session = session

    def add_msg(self, sender, receiver, msg, msg_type, timestamp)->bool:
        current_app.logger.debug(f"new msg, {sender}, {receiver}, {msg}, {msg_type}, {timestamp}")
        try:
            chatwith_ops = ChatWithOps(self.session)
            succeed = chatwith_ops.upsert_pair(sender=sender, receiver=receiver)
            if not succeed:
                raise Exception('Failed to upsert pair')

            chatmsg = ChatMsg(
                sender=sender,
                receiver=receiver,
                msg=msg,
                msg_type=msg_type,
                timestamp=timestamp,
            )

            self.session.add(chatmsg)
            self.session.commit()
            current_app.logger.debug(f"added msg")
            return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to add msg, error {str(e)}")
        return False

    def get_msgs(self, p1, p2, before_timestamp, latest_n)->list:
        try:
            msgs = self.session.query(ChatMsg).filter(
                db.and_(
                    db.or_(
                        db.and_(ChatMsg.sender == p1, ChatMsg.receiver == p2),
                        db.and_(ChatMsg.sender == p2, ChatMsg.receiver == p1)
                    ),
                    ChatMsg.timestamp < before_timestamp
                )
            ).order_by(db.desc(ChatMsg.timestamp)).limit(latest_n).all()
            current_app.logger.debug(f'len of all msgs {len(msgs)}')
            return [msg.to_dict() for msg in msgs]
        except Exception as e:
            current_app.logger.debug(f'failed to get msgs, error {str(e)}')
            return []

class CallRecord(db.Model):
    __tablename__ = 'CALL_RECORD'

    id = db.Column(db.String, primary_key=True) # id == appointment_id + '--' + idx
    type = db.Column(db.Integer, nullable=False) # 0 for audio, 1 for video
    appointment_id = db.Column(db.String, db.ForeignKey('APPOINTMENT.id'), nullable=False)
    idx = db.Column(db.Integer, nullable=False) # [0, inf)
    caller = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    callee = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    start_timestamp = db.Column(db.REAL, nullable=False)

    accept_timestamp = db.Column(db.REAL, nullable=True)
    hang_up_by = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=True)
    end_timestamp = db.Column(db.REAL, nullable=True)

    __table_args__ = (
        db.Index('index_CALL_RECORD_appointment_id', 'appointment_id', unique=False),
        db.Index('index_CALL_RECORD_caller', 'caller', unique=False),
        db.Index('index_CALL_RECORD_callee', 'callee', unique=False),
    )

    def to_dict(self):
        return {
            'type' : self.type,
            'appointment_id' : self.appointment_id,
            'idx' : self.idx,
            'caller' : self.caller,
            'callee' : self.callee,
            'start_timestamp' : self.start_timestamp,
            'accept_timestamp' : self.accept_timestamp,
            'hang_up_by' : self.hang_up_by,
            'end_timestamp' : self.end_timestamp,
        }

class CallRecordOps:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def get_id(appointment_id, idx):
        return f'{appointment_id}--{idx}'

    def start(self, appointment_id, type, caller, callee, timestamp)->str:
        current_app.logger.debug(f"start call, {appointment_id}, {type}, {caller}, {callee}, {timestamp}")
        try:
            records = self.session.query(CallRecord).filter_by(
                appointment_id=appointment_id
            ).order_by(CallRecord.idx).all()
            idx = len(records)

            id = CallRecordOps.get_id(appointment_id=appointment_id, idx=idx)
            call_record = CallRecord(
                id=id,
                type=type,
                appointment_id=appointment_id,
                idx=idx,
                caller=caller,
                callee=callee,
                start_timestamp=timestamp,
            )

            self.session.add(call_record)
            self.session.commit()
            current_app.logger.debug(f"added call record")
            return call_record.id
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to add call record, error {str(e)}")
        return None

    def accept(self, appointment_id, timestamp)->str:
        current_app.logger.debug(f"accept call, {appointment_id}, {timestamp}")
        try:
            records = self.session.query(CallRecord).filter_by(
                appointment_id=appointment_id
            ).order_by(CallRecord.idx).all()
            if len(records) == 0:
                raise Exception(f'Failed to record accept call before start: {appointment_id}')

            idx = len(records) - 1
            id = CallRecordOps.get_id(appointment_id=appointment_id, idx=idx)
            call_record = self.session.query(CallRecord).filter_by(id=id).first()
            call_record.accept_timestamp=timestamp

            self.session.commit()
            current_app.logger.debug(f"updated call accept record")
            return call_record.id
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to update call accept record, error {str(e)}")
        return None

    def end(self, appointment_id, by_user, timestamp)->str:
        current_app.logger.debug(f"end call, {appointment_id}, {by_user}, {timestamp}")
        try:
            records = self.session.query(CallRecord).filter_by(
                appointment_id=appointment_id
            ).order_by(CallRecord.idx).all()
            if len(records) == 0:
                raise Exception(f'Failed to record end call before start: {appointment_id}')

            idx = len(records) - 1
            id = CallRecordOps.get_id(appointment_id=appointment_id, idx=idx)
            call_record = self.session.query(CallRecord).filter_by(id=id).first()
            call_record.hang_up_by=by_user
            call_record.end_timestamp=timestamp

            self.session.commit()
            current_app.logger.debug(f"updated call end record")
            return call_record.id
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to update call end record, error {str(e)}")
        return None

    def get_records(self, appointment_id)->list:
        try:
            records = self.session.query(CallRecord).filter_by(
                appointment_id=appointment_id
            ).order_by(CallRecord.idx).all()
            current_app.logger.debug(f'len of all records {len(records)}')
            return [record.to_dict() for record in records]
        except Exception as e:
            current_app.logger.debug(f'failed to get records, error {str(e)}')
            return []

class Transfer(db.Model):
    __tablename__ = 'TRANSFER'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.String, nullable=False)
    from_user = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    to_user = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    value = db.Column(db.REAL, nullable=False)
    timestamp = db.Column(db.REAL, nullable=False)

    __table_args__ = (
        db.Index('index_Transfer_order_id', 'order_id', unique=False),
        db.Index('index_Transfer_from_user', 'from_user', unique=False),
        db.Index('index_Transfer_to_user', 'to_user', unique=False),
    )

    def to_dict(self):
        return {
            'order_id' : self.order_id,
            'from_user' : self.from_user,
            'to_user' : self.to_user,
            'value' : self.value,
            'timestamp' : self.timestamp,
        }

class TransferOps:
    def __init__(self, session):
        self.session = session

    def transfer(self, order_id, from_user, to_user, value, timestamp)->int:
        current_app.logger.debug(f"transfer, {order_id}, {from_user}, {to_user}, {value}, {timestamp}")
        try:
            tx = Transfer(order_id=order_id, from_user=from_user, to_user=to_user, value=value, timestamp=timestamp)
            self.session.add(tx)
            self.session.commit()
            current_app.logger.debug(f"recorded tx, {order_id}, {from_user}, {to_user}, {value}, {timestamp}")
            return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to add tx, {order_id}, error {str(e)}")
        return False


# Only used to record system accounts
class BalanceCNY(db.Model):
    __tablename__ = 'BALANCE_CNY'

    user_id = db.Column(db.Integer, db.ForeignKey('USER.id'), primary_key=True, nullable=False)
    balance = db.Column(db.REAL, nullable=False)

    def to_dict(self):
        return {
            'user_id' : self.user_id,
            'balance' : self.balance,
        }

# Balance in zchat
class Balance(db.Model):
    __tablename__ = 'BALANCE'

    user_id = db.Column(db.Integer, db.ForeignKey('USER.id'), primary_key=True, nullable=False)
    balance = db.Column(db.REAL, nullable=False)
    balance_locking = db.Column(db.REAL, nullable=False)
    total_income = db.Column(db.REAL, nullable=False)

    def to_dict(self):
        return {
            'user_id' : self.user_id,
            'balance' : self.balance,
            'balance_locking' : self.balance_locking,
            'total_income' : self.total_income,
        }

class BalanceOps:
    def __init__(self, session):
        self.session = session

    def balance_of(self, user_id)->dict:
        balance = self.session.query(Balance).filter_by(user_id=user_id).first()
        if balance:
            return balance.to_dict()
        else:
            return {
                'user_id' : user_id,
                'balance' : 0.0,
                'balance_locking' : 0.0,
                'total_income' : 0.0,
            }

    def deposit(self, user, amount, order_id)->bool:
        current_app.logger.debug(f"deposit, {user}, {amount}, {order_id}")
        try:
            if amount <= 0:
                current_app.logger.debug(f"amount is invalid, {amount}")
                return False

            balance = self.session.query(Balance).filter_by(user_id=user).first()
            if balance:
                b = balance.balance
                bb = b + amount
                if bb >= amount and bb > b and bb - amount == b:
                    balance.balance = bb
                else:
                    current_app.logger.debug(f"failed to change balance, {b}, {amount}, {bb}")
                    return False
            else:
                balance = Balance(user_id=user, balance=amount, balance_locking=0, total_income=0)
                self.session.add(balance)

            transfer_ops = TransferOps(self.session)
            succeed = transfer_ops.transfer(
                order_id=order_id,
                from_user=SYSTEM_ACCOUNT, # TODO change to system account
                to_user=user,
                value=amount,
                timestamp=time.time(),
            )

            system_balance_cny = self.session.query(BalanceCNY).filter_by(user_id=SYSTEM_ACCOUNT).first()
            if system_balance_cny:
                system_balance_cny.balance = system_balance_cny.balance + amount
            else:
                system_balance_cny = BalanceCNY(user_id=SYSTEM_ACCOUNT, balance=amount)
                self.session.add(system_balance_cny)

            if not succeed:
                raise Exception(f'Failed to record tx, order id: {order_id}')

            self.session.commit()
            current_app.logger.debug(f"deposited {amount} for user {user}")
            return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to deposit, error {str(e)}")
        return False

    def withdraw(self, user, amount, order_id)->bool:
        current_app.logger.debug(f"withdraw, {user}, {amount}, {order_id}")
        try:
            if amount <= 0:
                current_app.logger.debug(f"amount is invalid, {amount}")
                return False

            balance = self.session.query(Balance).filter_by(user_id=user).first()
            if balance:
                b = balance.balance
                bb = b - amount
                if bb >= 0 and bb < b and bb + amount == b:
                    balance.balance = bb
                else:
                    current_app.logger.debug(f"failed to change balance, {b}, {amount}, {bb}")
                    return False
            else:
                current_app.logger.debug(f"balance is invalid, {user}")
                return False

            transfer_ops = TransferOps(self.session)
            succeed = transfer_ops.transfer(
                order_id=order_id,
                from_user=user,
                to_user=-2, # TODO change to outer user account
                value=amount,
                timestamp=time.time(),
            )
            if not succeed:
                raise Exception(f'Failed to record tx, order id: {order_id}')

            system_balance_cny = self.session.query(BalanceCNY).filter_by(user_id=SYSTEM_ACCOUNT).first()
            if system_balance_cny and system_balance_cny.balance >= amount:
                system_balance_cny.balance = system_balance_cny.balance - amount
            else:
                raise Exception(f'No system account, failed to withdraw: {order_id}')

            self.session.commit()
            current_app.logger.debug(f"withdraw {amount} for user {user}")
            return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to deposit, error {str(e)}")
        return False

    def transfer(self, from_user, to_user, amount, order_id)->bool:
        current_app.logger.debug(f"transfer, {from_user}, {to_user}, {amount}, {order_id}")
        try:
            if amount <= 0:
                current_app.logger.debug(f"amount is invalid, {amount}")
                return False

            fb = self.session.query(Balance).filter_by(user_id=from_user).first()
            if fb is None:
                current_app.logger.debug(f"from_user and balance is invalid, {from_user}")
                return False

            tb = self.session.query(Balance).filter_by(user_id=to_user).first()
            if tb is None:
                tb = Balance(user_id=to_user, balance=0, balance_locking=0, total_income=0)
                self.session.add(tb)

            sb = self.session.query(Balance).filter_by(user_id=SYSTEM_ACCOUNT).first()
            if sb is None:
                sb = Balance(user_id=SYSTEM_ACCOUNT, balance=0, balance_locking=0, total_income=0)
                self.session.add(sb)

            to_amount = amount * PLATFORM_DISCOUNT
            to_sb_amount = amount * (1 - PLATFORM_DISCOUNT)

            fbb = fb.balance
            tbb = tb.balance_locking
            fbb_ = fbb - amount
            tbb_ = tbb + to_amount
            if fbb_ >= 0 and fbb_ < fbb and fbb_ + amount == fbb and \
                tbb_ > tbb and tbb_ - to_amount == tbb:
                fb.balance = fbb_
                tb.balance_locking = tbb_
                tb.total_income = tb.total_income + tbb_
                sb.balance = sb.balance + to_sb_amount
            else:
                current_app.logger.debug(f"failed to change balance, {fbb}, {fbb_}, {tbb}, {tbb_}, {amount}, {to_amount}")
                raise Exception(f"failed to change balance, {fbb}, {fbb_}, {tbb}, {tbb_}, {amount}, {to_amount}")

            transfer_ops = TransferOps(self.session)
            succeed = transfer_ops.transfer(
                order_id=order_id,
                from_user=from_user,
                to_user=to_user,
                value=to_amount,
                timestamp=time.time(),
            )

            if not succeed:
                raise Exception(f'Failed to record tx, order id: {order_id}, to {to_user}')

            succeed = transfer_ops.transfer(
                order_id=order_id,
                from_user=from_user,
                to_user=SYSTEM_ACCOUNT,
                value=to_sb_amount,
                timestamp=time.time(),
            )

            if not succeed:
                raise Exception(f'Failed to record tx, order id: {order_id}, to {SYSTEM_ACCOUNT}')

            self.session.commit()
            current_app.logger.debug(f"transferd from {from_user} to {to_user} with amount {amount}, {to_amount} for order_id {order_id}")
            return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to transfer, error {str(e)}")
        return False

    def refund(self, from_user, to_user, amount, order_id)->bool:
        current_app.logger.debug(f"refund, {from_user}, {to_user}, {amount}, {order_id}")
        try:
            if amount <= 0:
                current_app.logger.debug(f"amount is invalid, {amount}")
                return False

            fb = self.session.query(Balance).filter_by(user_id=from_user).first()
            if fb is None:
                current_app.logger.debug(f"from_user and balance is invalid, {from_user}")
                return False

            tb = self.session.query(Balance).filter_by(user_id=to_user).first()
            if tb is None:
                current_app.logger.debug(f"to_user and balance is invalid, {to_user}")
                return False

            sb = self.session.query(Balance).filter_by(user_id=SYSTEM_ACCOUNT).first()
            if sb is None:
                current_app.logger.debug(f"system account and balance is invalid, {SYSTEM_ACCOUNT}")
                return False

            to_amount = amount * PLATFORM_DISCOUNT
            to_sb_amount = amount * (1 - PLATFORM_DISCOUNT)

            fbb = fb.balance
            tbb = tb.balance_locking
            fbb_ = fbb + amount
            tbb_ = tbb - to_amount
            if fbb_ > fbb and fbb_ - amount == fbb and \
                tbb_ >= 0 and tbb_ < tbb and tbb_ + to_amount == tbb and \
                    sb.balance - to_sb_amount >= 0:
                fb.balance = fbb_
                tb.balance_locking = tbb_
                tb.total_income = tb.total_income - tbb_
                sb.balance = sb.balance - to_sb_amount
            else:
                current_app.logger.debug(f"failed to change balance, {fbb}, {fbb_}, {tbb}, {tbb_}, {amount}, {to_amount}, {to_sb_amount}, {sb.balance}")
                raise Exception(f"failed to change balance, {fbb}, {fbb_}, {tbb}, {tbb_}, {amount}, {to_amount}, {to_sb_amount}, {sb.balance}")

            transfer_ops = TransferOps(self.session)
            succeed = transfer_ops.transfer(
                order_id=order_id,
                from_user=to_user, # NOTE this is refund, the order is reversed
                to_user=from_user,
                value=to_amount,
                timestamp=time.time(),
            )
            if not succeed:
                raise Exception(f'Failed to record tx, order id: {order_id}, refund {from_user} from {to_user}')

            succeed = transfer_ops.transfer(
                order_id=order_id,
                from_user=SYSTEM_ACCOUNT, # NOTE this is refund, the order is reversed
                to_user=from_user,
                value=to_sb_amount,
                timestamp=time.time(),
            )

            if not succeed:
                raise Exception(f'Failed to record tx, order id: {order_id}, refund {from_user} from {SYSTEM_ACCOUNT}')

            self.session.commit()
            current_app.logger.debug(f"refund for {from_user} from {to_user} of amount {amount}, {to_amount} for order_id {order_id}")
            return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to refund, error {str(e)}")
        return False

    def unlock(self, user, amount, order_id)->bool:
        current_app.logger.debug(f"unlock, {user}, {amount}, {order_id}")
        try:
            if amount <= 0:
                current_app.logger.debug(f"amount is invalid, {amount}")
                return False

            balance = self.session.query(Balance).filter_by(user_id=user).first()
            if balance is None:
                current_app.logger.debug(f"balance is invalid, {user}")
                return False

            b = balance.balance
            bl = balance.balance_locking
            b_ = b + amount
            bl_ = bl - amount
            if b_ > b and b_ - b == amount and \
                bl_ >= 0 and bl_ < bl and bl_ + amount == bl and \
                    b + bl == b_ + bl_:
                balance.balance = b_
                balance.balance_locking = bl_
            else:
                current_app.logger.debug(f"failed to unlock balance, {b}, {bl}, {b_}, {bl_}, {amount}")
                raise Exception(f"failed to unlock balance, {b}, {bl}, {b_}, {bl_}, {amount}")

            self.session.commit()
            current_app.logger.debug(f"unlock {user} with amount {amount} for order_id {order_id}")
            return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to unlock, error {str(e)}")
        return False

    def check_all(self)->bool:
        total_balances = self.session.query(db.func.sum(Balance.balance)).scalar()
        total_balances_locking = self.session.query(db.func.sum(Balance.balance_locking)).scalar()
        total_balances_cny = self.session.query(db.func.sum(BalanceCNY.balance)).scalar()
        return total_balances + total_balances_locking == total_balances_cny

class AppointmentStage(Enum):
    # after newbie choosed a time and confirmed, before delivered, can go canceled, but count “失约次数”
    Created = 0

    # after expert confirmed, if not confirm in limit time, go to canceled
    Confirmed = 1

    # after newbie finished payment, if not pay in limit time, go to canceled
    Paied = 2

    # after video/voice call finished
    Delivered = 3

    # after comment submitted, if not comment in limit time, 5 star and go to finished
    Commented = 4

    # if has dispute, platform will handle it, normal workflow has no button to this stage
    Disputed = 5

    DisputeHandled = 6

    # final stage, if from paied, refund
    Canceled = 7

    # final stage, if no dispute or denied, pay to expert, else refund newbie
    Finished = 8

class Appointment(db.Model):
    __tablename__ = 'APPOINTMENT'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    type = db.Column(db.Integer, nullable=False, default=0)
    stage = db.Column(db.Integer, nullable=False, default=0)

    # create
    expert = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    newbie = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    createTimestamp = db.Column(db.REAL, nullable=False)

    # set time
    appointmentTimestamp = db.Column(db.REAL, nullable=True)

    # confirm
    confirmTimestamp = db.Column(db.REAL, nullable=True)

    # pay
    paymentPrice = db.Column(db.REAL, nullable=True)
    paymentTimestamp = db.Column(db.REAL, nullable=True)
    paymentOrderId = db.Column(db.String, nullable=True)

    # deliver
    appointmentMeetingRecordId = db.Column(db.String, nullable=True)
    deliverTimestamp = db.Column(db.REAL, nullable=True)

    # comment
    commentTimestamp = db.Column(db.REAL, nullable=True)
    commentContent = db.Column(db.String, nullable=True)
    commentRating = db.Column(db.REAL, nullable=True)

    # dispute, by newbie
    disputeContent = db.Column(db.String, nullable=True)
    disputeTimestamp = db.Column(db.REAL, nullable=True)

    # dispute handling, by platform admin
    disputeHandleAgree = db.Column(db.Integer, nullable=True)
    disputeHandleContent = db.Column(db.String, nullable=True)
    disputeHandleTimestamp = db.Column(db.REAL, nullable=True)

    # cancel
    asNoCredit = db.Column(db.Integer, nullable=False, default=0)

    # canceled or finished
    finishTimestamp = db.Column(db.REAL, nullable=True)

    __table_args__ = (
        db.Index('index_APPOINTMENT_expert', 'expert', unique=False),
        db.Index('index_APPOINTMENT_newbie', 'newbie', unique=False),
        db.Index('index_APPOINTMENT_stage', 'stage', unique=False),
    )

    def to_dict(self):
        return {
            'id' : self.id,
            'type' : self.type,
            'stage' : self.stage,

            'expert' : self.expert,
            'newbie' : self.newbie,
            'createTimestamp' : self.createTimestamp,

            'appointmentTimestamp' : self.appointmentTimestamp,

            'confirmTimestamp' : self.confirmTimestamp,

            'paymentPrice' : self.paymentPrice,
            'paymentTimestamp' : self.paymentTimestamp,
            'paymentOrderId' : self.paymentOrderId,

            'deliverTimestamp' : self.deliverTimestamp,
            'appointmentMeetingRecordId' : self.appointmentMeetingRecordId,

            'commentTimestamp' : self.commentTimestamp,
            'commentContent' : self.commentContent,
            'commentRating' : self.commentRating,

            'disputeContent' : self.disputeContent,
            'disputeTimestamp' : self.disputeTimestamp,

            'disputeHandleAgree' : self.disputeHandleAgree,
            'disputeHandleContent' : self.disputeHandleContent,
            'disputeHandleTimestamp' : self.disputeHandleTimestamp,

            'asNoCredit' : self.asNoCredit,

            'finishTimestamp' : self.finishTimestamp,
        }

class AppointmentOps:
    def __init__(self, session):
        self.session = session

    def create_appointment(self, type, expert, newbie)->str:
        current_app.logger.debug(f"create_appointment, {type}, {expert}, {newbie}")
        try:
            appointment = Appointment(
                type=type,
                expert=expert,
                newbie=newbie,
                createTimestamp=time.time(),
            )

            self.session.add(appointment)
            self.session.commit()
            current_app.logger.debug(f"added appointment")
            return appointment.id
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to add appointment, error {str(e)}")
        return None

    def update_timestamp(self, id, newbie_id, timestamp)->bool:
        current_app.logger.debug(f"update_timestamp, {id}, {newbie_id}, {timestamp}")
        try:
            appointment = self.session.query(Appointment).filter_by(id=id).first()
            if appointment:
                if newbie_id != appointment.newbie:
                    current_app.logger.debug(f"update_timestamp not authed {id}, {newbie_id}, {appointment.newbie}")
                    return False

                if appointment.stage == AppointmentStage.Created.value:
                    appointment.appointmentTimestamp = timestamp
                    self.session.commit()
                    current_app.logger.debug(f"updated appointment {id}")
                    return True
                else:
                    current_app.logger.debug(f"invalid appointment stage, {id}, {appointment.stage}")
                    return False
            else:
                current_app.logger.debug(f"appointment does not exists {id}")
                False
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to update appointment, error {str(e)}")
        return False

    def newbie_cancel(self, id, newbie_id)->bool:
        current_app.logger.debug(f"newbie_cancel, {id}, {newbie_id}")
        try:
            appointment = self.session.query(Appointment).filter_by(id=id).first()
            if appointment:
                if newbie_id != appointment.newbie:
                    current_app.logger.debug(f"newbie_canceled not authed {id}, {newbie_id}, {appointment.newbie}")
                    return False

                if appointment.stage == AppointmentStage.Created.value or \
                   appointment.stage == AppointmentStage.Confirmed.value or \
                   appointment.stage == AppointmentStage.Paied.value:

                    if appointment.appointmentTimestamp and appointment.appointmentTimestamp < time.time():
                        current_app.logger.debug(f"cancel appointment after appointment timestamp, not allowed, {id}")
                        return False

                    if appointment.stage == AppointmentStage.Confirmed.value or \
                       appointment.stage == AppointmentStage.Paied.value:
                        appointment.asNoCredit = 1

                        # if paied, refund newbie
                        if appointment.stage == AppointmentStage.Paied.value:
                            # refund
                            balance_ops = BalanceOps(session=self.session)
                            succeed = balance_ops.refund(
                                from_user=appointment.newbie,
                                to_user=appointment.expert,
                                amount=appointment.paymentPrice,
                                order_id=appointment.paymentOrderId)
                            if not succeed:
                                raise Exception(f'Failed to refund/cancel, id: {id}')

                    appointment.stage = AppointmentStage.Canceled.value
                    appointment.finishTimestamp = time.time()

                    self.session.commit()
                    current_app.logger.debug(f"newbie_canceled appointment {id}")
                    return True
                else:
                    current_app.logger.debug(f"invalid appointment stage, {id}, {appointment.stage}")
                    return False
            else:
                current_app.logger.debug(f"appointment does not exists {id}")
                False
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to update appointment, error {str(e)}")
        return False

    def expert_confirm(self, id, expert_id)->bool:
        current_app.logger.debug(f"expert_confirm, {id}, {expert_id}")
        try:
            appointment = self.session.query(Appointment).filter_by(id=id).first()
            if appointment:
                if expert_id != appointment.expert:
                    current_app.logger.debug(f"expert_confirm not authed {id}, {expert_id}, {appointment.expert}")
                    return False

                if appointment.stage == AppointmentStage.Created.value:
                    appointment.stage = AppointmentStage.Confirmed.value
                    appointment.confirmTimestamp = time.time()

                    self.session.commit()
                    current_app.logger.debug(f"expert_confirm appointment {id}")
                    return True
                else:
                    current_app.logger.debug(f"invalid appointment stage, {id}, {appointment.stage}")
                    return False
            else:
                current_app.logger.debug(f"appointment does not exists {id}")
                False
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to update appointment, error {str(e)}")
        return False

    def newbie_pay(self, id, newbie_id, price, order_id)->bool:
        current_app.logger.debug(f"newbie_pay, {id}, {newbie_id}, {price}, {order_id}")
        try:
            appointment = self.session.query(Appointment).filter_by(id=id).first()
            if appointment:
                if newbie_id != appointment.newbie:
                    current_app.logger.debug(f"newbie_pay not authed {id}, {newbie_id}, {appointment.newbie}")
                    return False

                if appointment.stage == AppointmentStage.Confirmed.value:
                    appointment.paymentPrice = price
                    appointment.paymentOrderId = order_id
                    appointment.paymentTimestamp = time.time()
                    appointment.stage = AppointmentStage.Paied.value

                    # transfer here
                    balance_ops = BalanceOps(session=self.session)
                    succeed = balance_ops.deposit(user=newbie_id, amount=price, order_id=order_id)
                    if succeed:
                        succeed = balance_ops.transfer(
                            from_user=newbie_id,
                            to_user=appointment.expert,
                            amount=price,
                            order_id=order_id,
                        )
                    else:
                        raise Exception(f'Failed to pay, id: {id}')

                    self.session.commit()
                    current_app.logger.debug(f"newbie_pay appointment {id}")
                    return True
                else:
                    current_app.logger.debug(f"invalid appointment stage, {id}, {appointment.stage}")
                    return False
            else:
                current_app.logger.debug(f"appointment does not exists {id}")
                False
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to update appointment, error {str(e)}")
        return False

    def platform_deliver(self, id, record_id)->bool:
        current_app.logger.debug(f"platform_deliver, {id}, {record_id}")
        try:
            appointment = self.session.query(Appointment).filter_by(id=id).first()
            if appointment:
                if appointment.stage == AppointmentStage.Paied.value:
                    appointment.appointmentMeetingRecordId = record_id
                    appointment.deliverTimestamp  = time.time()
                    appointment.stage = AppointmentStage.Delivered.value

                    self.session.commit()
                    current_app.logger.debug(f"platform_deliver appointment {id}")
                    return True
                else:
                    current_app.logger.debug(f"invalid appointment stage, {id}, {appointment.stage}")
                    return False
            else:
                current_app.logger.debug(f"appointment does not exists {id}")
                False
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to update appointment, error {str(e)}")
        return False

    def newbie_comment(self, id, newbie_id, content, rating)->bool:
        current_app.logger.debug(f"newbie_comment, {id}, {newbie_id}, {content}, {rating}")
        try:
            appointment = self.session.query(Appointment).filter_by(id=id).first()
            if appointment:
                if newbie_id != appointment.newbie:
                    current_app.logger.debug(f"newbie_comment not authed {id}, {newbie_id}, {appointment.newbie}")
                    return False

                if appointment.stage == AppointmentStage.Delivered.value:
                    appointment.stage = AppointmentStage.Commented.value
                    appointment.commentContent = content
                    appointment.commentRating = rating
                    appointment.commentTimestamp = time.time()

                    self.session.commit()
                    current_app.logger.debug(f"newbie_comment appointment {id}")
                    return True
                else:
                    current_app.logger.debug(f"invalid appointment stage, {id}, {appointment.stage}")
                    return False
            else:
                current_app.logger.debug(f"appointment does not exists {id}")
                False
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to update appointment, error {str(e)}")
        return False

    def newbie_dispute(self, id, newbie_id, content)->bool:
        current_app.logger.debug(f"newbie_dispute, {id}, {newbie_id}, {content}")
        try:
            appointment = self.session.query(Appointment).filter_by(id=id).first()
            if appointment:
                if newbie_id != appointment.newbie:
                    current_app.logger.debug(f"newbie_comment not authed {id}, {newbie_id}, {appointment.newbie}")
                    return False

                if appointment.stage == AppointmentStage.Commented.value:
                    appointment.stage = AppointmentStage.Disputed.value
                    appointment.disputeContent = content
                    appointment.disputeTimestamp = time.time()

                    self.session.commit()
                    current_app.logger.debug(f"newbie_dispute appointment {id}")
                    return True
                else:
                    current_app.logger.debug(f"invalid appointment stage, {id}, {appointment.stage}")
                    return False
            else:
                current_app.logger.debug(f"appointment does not exists {id}")
                False
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to update appointment, error {str(e)}")
        return False

    def platform_handle_dispute(self, id, agree, content)->bool:
        current_app.logger.debug(f"platform_handle_dispute, {id}, {agree}, {content}")
        try:
            appointment = self.session.query(Appointment).filter_by(id=id).first()
            if appointment:
                if appointment.stage == AppointmentStage.Disputed.value:
                    appointment.stage = AppointmentStage.DisputeHandled.value
                    appointment.disputeHandleAgree = 1 if agree else 0
                    appointment.disputeHandleContent = content
                    appointment.disputeHandleTimestamp = time.time()

                    self.session.commit()
                    current_app.logger.debug(f"platform_handle_dispute appointment {id}")
                    return True
                else:
                    current_app.logger.debug(f"invalid appointment stage, {id}, {appointment.stage}")
                    return False
            else:
                current_app.logger.debug(f"appointment does not exists {id}")
                False
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to update appointment, error {str(e)}")
        return False

    def platform_finish_it(self, id)->bool:
        current_app.logger.debug(f"platform_finish_it , {id}")
        try:
            appointment = self.session.query(Appointment).filter_by(id=id).first()
            if appointment:
                if appointment.stage == AppointmentStage.Commented.value or \
                   appointment.stage == AppointmentStage.DisputeHandled.value:

                    appointment.finishTimestamp = time.time()
                    appointment.stage = AppointmentStage.Finished.value

                    # do payment or refund
                    balance_ops = BalanceOps(session=self.session)
                    if appointment.disputeHandleAgree == 1:
                        # refund
                        succeed = balance_ops.refund(
                            from_user=appointment.newbie,
                            to_user=appointment.expert,
                            amount=appointment.paymentPrice,
                            order_id=appointment.paymentOrderId)
                        if not succeed:
                            raise Exception(f'Failed to refund/finish, id: {id}')
                    else:
                        amount = appointment.paymentPrice * PLATFORM_DISCOUNT
                        succeed = balance_ops.unlock(
                            user=appointment.expert,
                            amount=amount,
                            order_id=appointment.paymentOrderId)
                        if not succeed:
                            raise Exception(f'Failed to unlock/finish, id: {id}')

                    self.session.commit()
                    current_app.logger.debug(f"platform_finish_it appointment {id}")
                    return True
                else:
                    current_app.logger.debug(f"invalid appointment stage, {id}, {appointment.stage}")
                    return False
            else:
                current_app.logger.debug(f"appointment does not exists {id}")
                False
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to update appointment, error {str(e)}")
        return False

    def get_appointment(self, id)->Appointment:
        try:
            appointment = self.session.query(Appointment).filter_by(id=id).first()
            return appointment
        except Exception as e:
            current_app.logger.debug(f'failed to get appointment, id {id}, error {str(e)}')
            return None

    def get_appointments_of_newbie(self, newbie)->list:
        try:
            appointments = self.session.query(Appointment).filter_by(
                newbie=newbie).order_by(db.desc(Appointment.createTimestamp)).all()
            current_app.logger.debug(f'len of all appointments {len(appointments)}')
            return [appointment.to_dict() for appointment in appointments]
        except Exception as e:
            current_app.logger.debug(f'failed to get appointments, error {str(e)}')
            return []

    def get_appointments_of_expert(self, expert)->list:
        try:
            appointments = self.session.query(Appointment).filter_by(
                expert=expert).order_by(db.desc(Appointment.createTimestamp)).all()
            current_app.logger.debug(f'len of all appointments {len(appointments)}')
            return [appointment.to_dict() for appointment in appointments]
        except Exception as e:
            current_app.logger.debug(f'failed to get appointments, error {str(e)}')
            return []

    def get_appointments_disputed(self)->list:
        try:
            appointments = self.session.query(Appointment).filter_by(
                stage=AppointmentStage.Disputed.value).order_by(Appointment.createTimestamp).all()
            current_app.logger.debug(f'len of all appointments {len(appointments)}')
            return [appointment.to_dict() for appointment in appointments]
        except Exception as e:
            current_app.logger.debug(f'failed to get appointments, error {str(e)}')
            return []

    def get_appointments_waiting_finish(self)->list:
        try:
            appointments = self.session.query(Appointment).filter(
                db.or_(
                    db.and_(
                        Appointment.stage==AppointmentStage.Commented.value,
                        Appointment.commentTimestamp<time.time()-24*60*60,
                    ),
                    Appointment.stage==AppointmentStage.DisputeHandled.value,
                )
            ).order_by(Appointment.createTimestamp).all()
            current_app.logger.debug(f'len of all appointments {len(appointments)}')
            return [appointment.to_dict() for appointment in appointments]
        except Exception as e:
            current_app.logger.debug(f'failed to get appointments, error {str(e)}')
            return []

    def get_comments_of(self, expert)->list:
        try:
            results = self.session.query(
                Appointment.newbie,
                Appointment.id,
                Appointment.commentRating,
                Appointment.commentContent,
                Appointment.commentTimestamp
            ).filter(
                db.and_(
                    Appointment.expert==expert,
                    Appointment.stage==AppointmentStage.Finished.value,
                )
            ).order_by(db.desc(Appointment.commentTimestamp)).all()
            current_app.logger.debug(f'len of all comments {len(results)}')
            return [{
                'newbie': result.newbie,
                'expert': expert,
                'id': result.id,
                'rating': result.commentRating,
                'content': result.commentContent,
                'timestamp': result.commentTimestamp,
            } for result in results]
        except Exception as e:
            current_app.logger.debug(f'failed to get comments, error {str(e)}')
            return []

    def get_comments_for_community(self, offset=0, limit=10)->list:
        try:
            results = self.session.query(
                Appointment.newbie,
                Appointment.expert,
                Appointment.id,
                Appointment.commentRating,
                Appointment.commentContent,
                Appointment.commentTimestamp
            ).filter(
                Appointment.stage==AppointmentStage.Finished.value,
            ).order_by(
                db.desc(Appointment.commentTimestamp)
            ).offset(
                offset=offset
            ).limit(
                limit=limit
            ).all()
            current_app.logger.debug(f'len of all comments {len(results)}')
            return [{
                'newbie': result.newbie,
                'expert': result.expert,
                'id': result.id,
                'rating': result.commentRating,
                'content': result.commentContent,
                'timestamp': result.commentTimestamp,
            } for result in results]
        except Exception as e:
            current_app.logger.debug(f'failed to get comments, error {str(e)}')
            return []

class MarkExpert(db.Model):
    __tablename__ = 'MARK_EXPERT'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    newbie = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)
    expert = db.Column(db.Integer, db.ForeignKey('USER.id'), nullable=False)

    __table_args__ = (
        db.Index('index_MARK_EXPERT_newbie', 'newbie', unique=False),
        db.Index('index_MARK_EXPERT_expert', 'expert', unique=False),
    )

    def to_dict(self):
        return {
            'newbie': self.newbie,
            'expert': self.expert,
        }

class MarkExpertOps:
    def __init__(self, session):
        self.session = session

    def add_mark(self, newbie, expert)->bool:
        current_app.logger.debug(f"add_mark, {newbie}, {expert}")
        try:
            all = self.session.query(
                MarkExpert,
            ).filter(
                MarkExpert.newbie==newbie,
                MarkExpert.expert==expert,
            ).all()

            if len(all) >= 1:
                current_app.logger.debug(f"mark already exists")
                return True

            mark = MarkExpert(newbie=newbie, expert=expert)
            self.session.add(mark)
            self.session.commit()
            current_app.logger.debug(f"added mark")
            return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to add mark, error {str(e)}")
        return False

    def remove_mark(self, newbie, expert)->bool:
        current_app.logger.debug(f"add_mark, {newbie}, {expert}")
        try:
            result = self.session.query(
                MarkExpert,
            ).filter(
                MarkExpert.newbie==newbie,
                MarkExpert.expert==expert,
            ).first()
            if result is not None:
                self.session.delete(result)
                self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            current_app.logger.debug(f"failed to remove mark, error {str(e)}")
        return False

    def get_marked_experts(self, newbie)->list:
        current_app.logger.debug(f"get_marked_experts, {newbie}")
        try:
            results = self.session.query(
                MarkExpert,
            ).filter(
                MarkExpert.newbie==newbie,
            ).order_by(db.desc(MarkExpert.id)).all()
            return [result.expert for result in results]
        except Exception as e:
            current_app.logger.debug(f"failed to get marked experts, error {str(e)}")
        return []

    def get_marked_by_count(self, expert)->int:
        current_app.logger.debug(f"get_marked_by_count, {expert}")
        try:
            result = self.session.query(
                MarkExpert,
            ).filter(
                MarkExpert.expert==expert,
            ).count()
            return result
        except Exception as e:
            current_app.logger.debug(f"failed to get marked by count, error {str(e)}")
        return 0

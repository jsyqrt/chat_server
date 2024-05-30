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
    email = db.Column(db.String, nullable=True)
    email_verified = db.Column(db.Integer, nullable=True)
    company = db.Column(db.String, nullable=True)
    title = db.Column(db.String, nullable=True)
    profession = db.Column(db.String, nullable=True)
    business = db.Column(db.String, nullable=True)

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
        db.Index('index_USER_email', 'email', unique=False),
        db.Index('index_USER_email_verified', 'email_verified', unique=False),
        db.Index('index_USER_company', 'company', unique=False),
        db.Index('index_USER_title', 'title', unique=False),
        db.Index('index_USER_profession', 'profession', unique=False),
        db.Index('index_USER_business', 'business', unique=False),

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
            'email' : self.email,
            'email_verified': self.email_verified,
            'company' : self.company,
            'title' : self.title,
            'profession': self.profession,
            'business': self.business,
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

    def update_basic(self, id, phone_number, nickname, gender, edubg, yearofwork, signature_text)->bool:
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

    def get_user(self, id)->User:
        try:
            user = self.session.query(User).filter_by(id=id).first()
            return user
        except Exception as e:
            current_app.logger.debug(f'failed to get users, error {str(e)}')
            return None

    def get_all_users(self)->list:
        try:
            users = self.session.query(User).all()
            current_app.logger.debug(f'len of all users {len(users)}')
            return [user.to_dict() for user in users]
        except Exception as e:
            current_app.logger.debug(f'failed to get all users, error {str(e)}')
            return []

# def init():
#     engine = create_engine('sqlite:///' + GlobalConfig['db_name'])
#     create_database(engine=engine)

#     Session = sessionmaker(bind=engine)
#     session = Session()

#     user_ops = UserOps(session=session)
#     paper_ops = PaperOps(session=session)

#     assert user_ops.create_user(name="Jason", tags="Newbie")
#     assert user_ops.create_user(name="Bob", tags="Newbie")
#     assert user_ops.create_user(name="Alice", tags="Newbie")
#     assert user_ops.update_user(name="Jason", new_tags="Master")

#     user = user_ops.get_user(name="Jason")
#     paper = {
#         'description': "This is a math test",
#         'tags': json.dumps(["math", "easy"]),
#         'created_by': user.id,
#         'questions': [
#             {
#                 'description': "what is the answer of 1+1?",
#                 'options': json.dumps(["1", "2", "3", "4"]),
#                 'answers': json.dumps(["2"]),
#             },
#             {
#                 'description': "what is the answer of 1*1?",
#                 'options': json.dumps(["1", "2", "3", "4"]),
#                 'answers': json.dumps(["1"]),
#             },
#         ]
#     }
#     assert paper_ops.create_paper(user_id=paper['created_by'], description=paper['description'], tags=paper['tags'], questions=paper['questions'])

#     user = user_ops.get_user(name="Alice")
#     paper = {
#         'description': "This is a physical test",
#         'tags': json.dumps(["physical", "easy"]),
#         'created_by': user.id,
#         'questions': [
#             {
#                 'description': "what is the speed of light?",
#                 'options': json.dumps(["1e8", "2e8", "3e8", "4e8"]),
#                 'answers': json.dumps(["3e8"]),
#             },
#             {
#                 'description': "what is the speed of sound?",
#                 'options': json.dumps(["4e2", "3e2", "2e2", "1e2"]),
#                 'answers': json.dumps(["3e2"]),
#             },
#         ]
#     }
#     assert paper_ops.create_paper(user_id=paper['created_by'], description=paper['description'], tags=paper['tags'], questions=paper['questions'])

#     user = user_ops.get_user(name="Bob")
#     answers = {
#         'paper_id': 1,
#         'answered_by': user.id,
#         'answers': [
#             {
#                 'question_id': 1,
#                 'answer_text': json.dumps(["2"]),
#             },
#             {
#                 'question_id': 2,
#                 'answer_text': json.dumps(["3"]),
#             },
#         ]
#     }
#     assert paper_ops.answer_paper(user_id=user.id, paper_id=1, answers=answers['answers'])

#     user = user_ops.get_user(name="Jason")
#     answers = {
#         'paper_id': 2,
#         'answered_by': user.id,
#         'answers': [
#             {
#                 'question_id': 1,
#                 'answer_text': json.dumps(["3e8"]),
#             },
#             {
#                 'question_id': 2,
#                 'answer_text': json.dumps(["3e2"]),
#             },
#         ]
#     }
#     assert paper_ops.answer_paper(user_id=user.id, paper_id=1, answers=answers['answers'])

#     session.close()

# def get():
#     engine = create_engine('sqlite:///' + GlobalConfig['db_name'])

#     Session = sessionmaker(bind=engine)
#     session = Session()

#     user_ops = UserOps(session=session)
#     paper_ops = PaperOps(session=session)

#     assert len(user_ops.get_all_users()) == 3

#     assert len(paper_ops.get_all_paper_ids()) == 2

#     alice = user_ops.get_user(name='Alice')
#     bob = user_ops.get_user(name='Bob')
#     jason = user_ops.get_user(name='Jason')

#     papers = paper_ops.get_papers_created_by(user_id=alice.id)
#     assert len(papers) == 1

#     papers = paper_ops.get_papers_created_by(user_id=bob.id)
#     assert len(papers) == 0

#     papers = paper_ops.get_papers_created_by(user_id=jason.id)
#     assert len(papers) == 1

#     papers = paper_ops.get_papers_answered_by(user_id=alice.id)
#     assert len(papers) == 0

#     papers = paper_ops.get_papers_answered_by(user_id=bob.id)
#     assert len(papers) == 1

#     papers = paper_ops.get_papers_answered_by(user_id=jason.id)
#     assert len(papers) == 1

#     paper_questions = paper_ops.get_paper_with_questions(paper_id=papers[0].Paper.id)
#     assert len(paper_questions) == 2

#     question_answers = paper_ops.get_questions_with_answers(paper_id=papers[0].Paper.id, user_id=jason.id)
#     assert len(question_answers) == 2

#     session.close()

# if __name__ == '__main__':
#     # init()
#     get()
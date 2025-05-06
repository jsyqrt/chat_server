import os
import json
import uuid
import time
from enum import Enum

from flask import current_app, url_for

from zchat.models.base import db
from zchat.nosql import add_mindmap_nosql, delete_mindmap_nosql

class RoadmapStatus(Enum):
    UNKNOWN = 0
    PRIVATE = 1
    PUBLIC = 2

# 使用db.Model定义SQLAlchemy模型
class Roadmap(db.Model):
    """学习路径模型"""
    __tablename__ = 'ROADMAP'

    roadmap_id = db.Column(db.String(255), primary_key=True)
    roadmap_icon = db.Column(db.String(255), nullable=False)
    roadmap_title = db.Column(db.String(255), nullable=False)
    roadmap_subtitle = db.Column(db.String(255), nullable=False)
    roadmap_type = db.Column(db.String(50), nullable=False) # official, user
    roadmap_kind = db.Column(db.String(50), nullable=False) # industry, job, skill, skill_group, topic
    roadmap_status = db.Column(db.Integer, nullable=False, default=RoadmapStatus.UNKNOWN.value) # 0->unknown, 1->private, 2->public
    roadmap_lang = db.Column(db.String(50), nullable=False, default='zh_CN') # zh_CN, en

    mindmap_id = db.Column(db.String(255), nullable=False)
    created_by = db.Column(db.String(255), nullable=True)

    industry_tag = db.Column(db.String(100), nullable=True)
    job_tag = db.Column(db.String(100), nullable=True)
    skill_tag = db.Column(db.String(100), nullable=True)

    create_timestamp = db.Column(db.REAL, nullable=True, default=time.time())
    update_timestamp = db.Column(db.REAL, nullable=True, default=time.time())

    viewed = db.Column(db.Integer, nullable=False, default=0)
    participanted = db.Column(db.Integer, nullable=False, default=0)
    completed = db.Column(db.Integer, nullable=False, default=0)
    favorited = db.Column(db.Integer, nullable=False, default=0)
    shared = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.Index('index_ROADMAP_title', 'roadmap_title', unique=False),
        db.Index('index_ROADMAP_subtitle', 'roadmap_subtitle', unique=False),
        db.Index('index_ROADMAP_type', 'roadmap_type', unique=False),
        db.Index('index_ROADMAP_kind', 'roadmap_kind', unique=False),
        db.Index('index_ROADMAP_status', 'roadmap_status', unique=False),
        db.Index('index_ROADMAP_lang', 'roadmap_lang', unique=False),
        db.Index('index_ROADMAP_mindmap_id', 'mindmap_id', unique=False),
        db.Index('index_ROADMAP_created_by', 'created_by', unique=False),
        db.Index('index_ROADMAP_industry_tag', 'industry_tag', unique=False),
        db.Index('index_ROADMAP_job_tag', 'job_tag', unique=False),
        db.Index('index_ROADMAP_skill_tag', 'skill_tag', unique=False),
        db.Index('index_ROADMAP_create_timestamp', 'create_timestamp', unique=False),
        db.Index('index_ROADMAP_update_timestamp', 'update_timestamp', unique=False),
        db.Index('index_ROADMAP_viewed', 'viewed', unique=False),
        db.Index('index_ROADMAP_participanted', 'participanted', unique=False),
        db.Index('index_ROADMAP_completed', 'completed', unique=False),
        db.Index('index_ROADMAP_favorited', 'favorited', unique=False),
        db.Index('index_ROADMAP_shared', 'shared', unique=False),
    )

    def to_dict(self):
        return {
            'id' : self.roadmap_id,
            'icon' : self.roadmap_icon,
            'title' : self.roadmap_title,
            'subtitle' : self.roadmap_subtitle,
            'type' : self.roadmap_type,
            'kind' : self.roadmap_kind,
            'status': self.roadmap_status,
            'lang': self.roadmap_lang,
            'mindmap_id': self.mindmap_id,
            'created_by': self.created_by,
            'industry_tag': self.industry_tag,
            'job_tag': self.job_tag,
            'skill_tag': self.skill_tag,
            'created_at': self.create_timestamp,
            'updated_at': self.update_timestamp,
            'viewed': self.viewed,
            'participanted': self.participanted,
            'completed': self.completed,
            'favorited': self.favorited,
            'shared': self.shared,
        }

class RoadmapInteraction(db.Model):
    __tablename__ = 'ROADMAP_INTERACTION'

    roadmap_id = db.Column(db.String(255))
    user_id = db.Column(db.String(255))
    viewed = db.Column(db.Integer, nullable=False, default=0)
    participanted = db.Column(db.Integer, nullable=False, default=0)
    completed = db.Column(db.Integer, nullable=False, default=0)
    favorited = db.Column(db.Integer, nullable=False, default=0)
    shared = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.PrimaryKeyConstraint('roadmap_id', 'user_id'),
        db.Index('index_ROADMAP_INTERACTION_user_id', 'user_id', unique=False),
        db.Index('index_ROADMAP_INTERACTION_viewed', 'viewed', unique=False),
        db.Index('index_ROADMAP_INTERACTION_participanted', 'participanted', unique=False),
        db.Index('index_ROADMAP_INTERACTION_completed', 'completed', unique=False),
        db.Index('index_ROADMAP_INTERACTION_favorited', 'favorited', unique=False),
        db.Index('index_ROADMAP_INTERACTION_shared', 'shared', unique=False),
    )

    def to_dict(self):
        return {
            'roadmap_id': self.roadmap_id,
            'user_id': self.user_id,
            'viewed': self.viewed,
            'participanted': self.participanted,
            'completed': self.completed,
            'favorited': self.favorited,
            'shared': self.shared,
        }

class RoadmapInteractionOps:
    def __init__(self, session):
        self.session = session

    def get_viewed(self, roadmap_id: str, user_id: str)->bool:
        interaction = self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, user_id=user_id).first()
        if interaction:
            return interaction.viewed == 1
        return False

    def get_viewed_roadmaps(self, user_id: str)->list:
        interactions = self.session.query(RoadmapInteraction).filter_by(user_id=user_id).all()
        return [interaction.roadmap_id for interaction in interactions if interaction.viewed == 1]

    def view(self, roadmap_id: str, user_id: str)->bool:
        interaction = self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, user_id=user_id).first()
        if interaction:
            if interaction.viewed == 0:
                interaction.viewed = 1
                roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
                if roadmap:
                    roadmap.viewed += 1
                self.session.commit()
                return True
        else:
            interaction = RoadmapInteraction(roadmap_id=roadmap_id, user_id=user_id, viewed=1)
            self.session.add(interaction)

            roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
            if roadmap:
                roadmap.viewed += 1

            self.session.commit()
            return True

    def participated(self, roadmap_id: str, user_id: str)->bool:
        interaction = self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, user_id=user_id).first()
        if interaction:
            return interaction.participanted == 1
        return False

    def participant(self, roadmap_id: str, user_id: str)->bool:
        interaction = self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, user_id=user_id).first()
        if interaction:
            if interaction.participanted == 0:
                interaction.participanted = 1
                roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
                if roadmap:
                    roadmap.participanted += 1

                self.session.commit()
                return True
        else:
            interaction = RoadmapInteraction(roadmap_id=roadmap_id, user_id=user_id, participanted=1)
            self.session.add(interaction)

            roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
            if roadmap:
                roadmap.participanted += 1

            self.session.commit()
            return True

    def get_participants_count_of_roadmap(self, roadmap_id: str)->int:
        from sqlalchemy import func, Integer
        return self.session.query(func.cast(func.count(RoadmapInteraction.user_id), Integer)).filter_by(roadmap_id=roadmap_id, participanted=1).scalar()

    def get_participants_count_of_user(self, user_id: str)->int:
        from sqlalchemy import func, Integer
        return self.session.query(func.cast(func.count(RoadmapInteraction.roadmap_id), Integer)).filter_by(user_id=user_id, participanted=1).scalar()

    def completion(self, roadmap_id: str, user_id: str)->bool:
        interaction = self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, user_id=user_id).first()
        if interaction:
            if interaction.completed == 0:
                interaction.participanted = 1
                interaction.completed = 1
                roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
                if roadmap:
                    roadmap.completed += 1

                self.session.commit()
                return True
        else:
            interaction = RoadmapInteraction(roadmap_id=roadmap_id, user_id=user_id, participanted=1, completed=1)
            self.session.add(interaction)

            roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
            if roadmap:
                roadmap.completed += 1

            self.session.commit()
            return True

    def favorite(self, roadmap_id: str, user_id: str)->bool:
        interaction = self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, user_id=user_id).first()
        if interaction:
            if interaction.favorited == 0:
                interaction.favorited = 1
                roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
                if roadmap:
                    roadmap.favorited += 1

                self.session.commit()
                return True
        else:
            interaction = RoadmapInteraction(roadmap_id=roadmap_id, user_id=user_id, favorited=1)
            self.session.add(interaction)

            roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
            if roadmap:
                roadmap.favorited += 1

            self.session.commit()
            return True

    def get_favorites(self, user_id: str)->list:
        interactions = self.session.query(RoadmapInteraction).filter_by(user_id=user_id).all()
        return [interaction.roadmap_id for interaction in interactions if interaction.favorited == 1]

    def un_favorite(self, roadmap_id: str, user_id: str)->bool:
        interaction = self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, user_id=user_id).first()
        if interaction:
            interaction.favorited = 0
            roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
            if roadmap:
                roadmap.favorited -= 1

            self.session.commit()
            return True
        return False

    def share(self, roadmap_id: str, user_id: str)->bool:
        interaction = self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, user_id=user_id).first()
        if interaction:
            if interaction.shared == 0:
                interaction.shared = 1
                roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
                if roadmap:
                    roadmap.shared += 1

            self.session.commit()
            return True
        else:
            interaction = RoadmapInteraction(roadmap_id=roadmap_id, user_id=user_id, shared=1)
            self.session.add(interaction)

            roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
            if roadmap:
                roadmap.shared += 1

            self.session.commit()
            return True

    def get_viewed_count_of_roadmap(self, roadmap_id: str)->int:
        from sqlalchemy import func, Integer
        return self.session.query(func.cast(func.count(RoadmapInteraction.user_id), Integer)).filter_by(roadmap_id=roadmap_id, viewed=1).scalar()

    def get_completions_count_of_roadmap(self, roadmap_id: str)->int:
        from sqlalchemy import func, Integer
        return self.session.query(func.cast(func.count(RoadmapInteraction.user_id), Integer)).filter_by(roadmap_id=roadmap_id, completed=1).scalar()

    def get_favorites_count_of_roadmap(self, roadmap_id: str)->int:
        from sqlalchemy import func, Integer
        return self.session.query(func.cast(func.count(RoadmapInteraction.user_id), Integer)).filter_by(roadmap_id=roadmap_id, favorited=1).scalar()

    def get_shares_count_of_roadmap(self, roadmap_id: str)->int:
        from sqlalchemy import func, Integer
        return self.session.query(func.cast(func.count(RoadmapInteraction.user_id), Integer)).filter_by(roadmap_id=roadmap_id, shared=1).scalar()

    def get_stats(self, roadmap_id: str)->dict:
        return {
            'viewed': self.get_viewed_count_of_roadmap(roadmap_id),
            'participants': self.get_participants_count_of_roadmap(roadmap_id),
            'completions': self.get_completions_count_of_roadmap(roadmap_id),
            'favorites': self.get_favorites_count_of_roadmap(roadmap_id),
            'shares': self.get_shares_count_of_roadmap(roadmap_id),
        }

class RoadmapOps:
    def __init__(self, session):
        self.session = session

    def create_roadmap(self, id, icon, title, subtitle, type, kind, status, lang, mindmap_id, created_by, industry_tag, job_tag, skill_tag)->Roadmap:
        try:
            roadmap = Roadmap(
                roadmap_id=id,
                roadmap_icon=icon,
                roadmap_title=title,
                roadmap_subtitle=subtitle,
                roadmap_type=type,
                roadmap_kind=kind,
                roadmap_status=status,
                roadmap_lang=lang,
                mindmap_id=mindmap_id,
                created_by=created_by,
                industry_tag=industry_tag,
                job_tag=job_tag,
                skill_tag=skill_tag,
            )
            self.session.add(roadmap)
            self.session.commit()
            return roadmap
        except Exception as e:
            self.session.rollback()
            current_app.logger.error(f'create_roadmap: {e}')
            return None

    def reset_official_roadmaps(self)->bool:
        # backend_cn.json
        # nodejs_cn.json
        # devops_cn.json
        # server-side-game-developer_cn.json
        # frontend_cn.json
        # computer-science_cn.json

        # python_cn.json
        # software-architect_cn.json
        # data-analyst_cn.json

        # nodejs.json
        # devops.json
        # server-side-game-developer.json
        # frontend.json
        # computer-science.json
        # python.json
        # software-architect.json
        # data-analyst.json
        # typescript.json
        # mlops.json
        # vue.json
        # aspnet-core.json
        # postgresql-dba.json
        # angular.json
        # qa.json
        # backend.json
        # cyber-security.json
        # blockchain.json
        # full-stack.json
        # android.json
        # system-design.json
        # javascript.json
        # technical-writer.json
        # game-developer.json
        # react.json
        # ux-design.json
        # sql.json

        items = [
            # nodejs.json
            {
                "id": "nodejs_cn.json",
                "icon": "⚡",
                "title": "Node.js编程",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "后端开发",
                "skill_tag": "Node.js",
                "lang": "zh_CN",
            },
            # devops.json
            {
                "id": "devops_cn.json",
                "icon": "🔄",
                "title": "DevOps工程师",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "后端开发",
                "skill_tag": "运维",
                "lang": "zh_CN",
            },
            # server-side-game-developer.json
            {
                "id": "server-side-game-developer_cn.json",
                "icon": "🎮",
                "title": "服务器端游戏开发",
                "subtitle": "游戏开发",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "游戏开发",
                "job_tag": "服务器端开发",
                "skill_tag": "服务端游戏开发",
                "lang": "zh_CN",
            },
            # frontend.json
            {
                "id": "frontend_cn.json",
                "icon": "🖥️",
                "title": "前端开发",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "前端开发",
                "skill_tag": "前端开发",
                "lang": "zh_CN",
            },
            # computer-science.json
            {
                "id": "computer-science_cn.json",
                "icon": "🧠",
                "title": "计算机科学",
                "subtitle": "基础知识",
                "type": "official",
                "kind": "concept",
                "status": 2,
                "industry_tag": "信息技术",
                "job_tag": "",
                "skill_tag": "计算机基础",
                "lang": "zh_CN",
            },
            # python.json
            {
                "id": "python_cn.json",
                "icon": "🐍",
                "title": "Python开发",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "后端开发",
                "skill_tag": "Python",
                "lang": "zh_CN",
            },
            # software-architect.json
            {
                "id": "software-architect_cn.json",
                "icon": "🏗️",
                "title": "软件架构师",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "架构师",
                "skill_tag": "软件架构",
                "lang": "zh_CN",
            },
            # data-analyst.json
            {
                "id": "data-analyst_cn.json",
                "icon": "📊",
                "title": "数据分析师",
                "subtitle": "数据科学",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "数据科学",
                "job_tag": "数据分析师",
                "skill_tag": "数据分析",
                "lang": "zh_CN",
            },
            # typescript.json
            {
                "id": "typescript_cn.json",
                "icon": "📘",
                "title": "TypeScript编程",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "前端开发",
                "skill_tag": "TypeScript",
                "lang": "zh_CN",
            },
            # mlops.json
            {
                "id": "mlops_cn.json",
                "icon": "🤖",
                "title": "MLOps工程师",
                "subtitle": "机器学习",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "机器学习",
                "job_tag": "机器学习工程师",
                "skill_tag": "机器学习运维",
                "lang": "zh_CN",
            },
            # vue.json
            {
                "id": "vue_cn.json",
                "icon": "🟢",
                "title": "Vue开发",
                "subtitle": "前端开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "前端开发",
                "skill_tag": "Vue",
                "lang": "zh_CN",
            },

            # postgresql-dba.json
            {
                "id": "postgresql-dba_cn.json",
                "icon": "🐘",
                "title": "PostgreSQL数据库管理",
                "subtitle": "数据库",
                "type": "official",
                "kind": "skill",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "后端开发",
                "skill_tag": "PostgreSQL",
                "lang": "zh_CN",
            },
            # angular.json
            {
                "id": "angular_cn.json",
                "icon": "🔺",
                "title": "Angular开发",
                "subtitle": "前端开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "前端开发",
                "skill_tag": "Angular",
                "lang": "zh_CN",
            },
            # qa.json
            {
                "id": "qa_cn.json",
                "icon": "🔍",
                "title": "QA测试工程师",
                "subtitle": "软件测试",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "测试工程师",
                "skill_tag": "QA",
                "lang": "zh_CN",
            },
            # backend_cn.json
            {
                "id": "backend_cn.json",
                "icon": "⚙️",
                "title": "后端开发",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "后端开发",
                "skill_tag": "后端开发",
                "lang": "zh_CN",
            },
            # cyber-security.json
            {
                "id": "cyber-security_cn.json",
                "icon": "🔒",
                "title": "网络安全",
                "subtitle": "安全",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "安全",
                "job_tag": "安全工程师",
                "skill_tag": "网络安全",
                "lang": "zh_CN",
            },
            # blockchain.json
            {
                "id": "blockchain_cn.json",
                "icon": "⛓️",
                "title": "区块链开发",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "后端开发",
                "skill_tag": "区块链",
                "lang": "zh_CN",
            },
            # full-stack.json
            {
                "id": "full-stack_cn.json",
                "icon": "🧰",
                "title": "全栈开发",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "全栈开发",
                "skill_tag": "全栈开发",
                "lang": "zh_CN",
            },
            # android.json
            {
                "id": "android_cn.json",
                "icon": "📱",
                "title": "Android开发",
                "subtitle": "移动开发",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "移动开发",
                "skill_tag": "Android",
                "lang": "zh_CN",
            },
            # system-design.json
            {
                "id": "system-design_cn.json",
                "icon": "📐",
                "title": "系统设计",
                "subtitle": "软件架构",
                "type": "official",
                "kind": "skill",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "架构师",
                "skill_tag": "系统设计",
                "lang": "zh_CN",
            },
            # javascript.json
            {
                "id": "javascript_cn.json",
                "icon": "💛",
                "title": "JavaScript编程",
                "subtitle": "前端开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "前端开发",
                "skill_tag": "JavaScript",
                "lang": "zh_CN",
            },
            # technical-writer.json
            {
                "id": "technical-writer_cn.json",
                "icon": "📝",
                "title": "技术文档写作",
                "subtitle": "技术写作",
                "type": "official",
                "kind": "skill",
                "status": 2,
                "industry_tag": "技术写作",
                "job_tag": "技术文案",
                "skill_tag": "技术文档写作",
                "lang": "zh_CN",
            },
            # game-developer.json
            {
                "id": "game-developer_cn.json",
                "icon": "🎲",
                "title": "游戏开发",
                "subtitle": "游戏开发",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "游戏开发",
                "job_tag": "游戏开发",
                "skill_tag": "游戏开发",
                "lang": "zh_CN",
            },
            # react.json
            {
                "id": "react_cn.json",
                "icon": "⚛️",
                "title": "React开发",
                "subtitle": "前端开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "前端开发",
                "skill_tag": "React",
                "lang": "zh_CN",
            },
            # ux-design.json
            {
                "id": "ux-design_cn.json",
                "icon": "🎨",
                "title": "UX设计",
                "subtitle": "设计",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "设计",
                "job_tag": "设计师",
                "skill_tag": "UX设计",
                "lang": "zh_CN",
            },
            # sql.json
            {
                "id": "sql_cn.json",
                "icon": "🗃️",
                "title": "SQL数据库",
                "subtitle": "数据库",
                "type": "official",
                "kind": "skill",
                "status": 2,
                "industry_tag": "软件开发",
                "job_tag": "后端开发",
                "skill_tag": "SQL",
                "lang": "zh_CN",
            },

# android.json
# angular.json
# aspnet-core.json
# backend.json
# blockchain.json
# computer-science.json
# cyber-security.json
# data-analyst.json
# devops.json
# frontend.json
# full-stack.json
# game-developer.json
# javascript.json
# mlops.json
# nodejs.json
# postgresql-dba.json
# python.json
# qa.json
# react.json
# server-side-game-developer.json
# software-architect.json
# sql.json
# system-design.json
# technical-writer.json
# typescript.json
# ux-design.json
# vue.json

            # android.json
            {
                "id": "android.json",
                "icon": "📱",
                "title": "Android Developer",
                "subtitle": "Mobile Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "Android Developer",
                "skill_tag": "Android",
                "lang": "en",
            },
            # angular.json
            {
                "id": "angular.json",
                "icon": "⚛️",
                "title": "Angular Developer",
                "subtitle": "Web Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "Full Stack Developer",
                "skill_tag": "Angular",
                "lang": "en",
            },
            # aspnet-core.json
            {
                "id": "aspnet-core.json",
                "icon": "🔧",
                "title": "ASP.NET Core Developer",
                "subtitle": "Web Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "Full Stack Developer",
                "skill_tag": "ASP.NET Core",
                "lang": "en",
            },
            # backend.json
            {
                "id": "backend.json",
                "icon": "⚙️",
                "title": "Backend Developer",
                "subtitle": "Software Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "Backend Developer",
                "skill_tag": "Backend",
                "lang": "en",
            },
            # blockchain.json
            {
                "id": "blockchain.json",
                "icon": "⛓️",
                "title": "Blockchain Developer",
                "subtitle": "Software Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "Backend Developer",
                "skill_tag": "Blockchain",
                "lang": "en",
            },
            # computer-science.json
            {
                "id": "computer-science.json",
                "icon": "💻",
                "title": "Computer Science",
                "subtitle": "Computer Science",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "Backend Developer",
                "skill_tag": "Computer Science",
                "lang": "en",
            },
            # cyber-security.json
            {
                "id": "cyber-security.json",
                "icon": "🔒",
                "title": "Cyber Security",
                "subtitle": "Cyber Security",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Cyber Security",
                "job_tag": "Cyber Security Engineer",
                "skill_tag": "Cyber Security",
                "lang": "en",
            },
            # data-analyst.json
            {
                "id": "data-analyst.json",
                "icon": "📊",
                "title": "Data Analyst",
                "subtitle": "Data Analysis",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Data Science",
                "job_tag": "Data Analyst",
                "skill_tag": "Data Analysis",
                "lang": "en",
            },
            # devops.json
            {
                "id": "devops.json",
                "icon": "🔧",
                "title": "DevOps Engineer",
                "subtitle": "DevOps",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "DevOps Engineer",
                "skill_tag": "DevOps",
                "lang": "en",
            },
            # frontend.json
            {
                "id": "frontend.json",
                "icon": "🎨",
                "title": "Frontend Developer",
                "subtitle": "Frontend Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "Frontend Developer",
                "skill_tag": "Frontend",
                "lang": "en",
            },
            # full-stack.json
            {
                "id": "full-stack.json",
                "icon": "🔄",
                "title": "Full Stack Developer",
                "subtitle": "Full Stack Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "Full Stack Developer",
                "skill_tag": "Full Stack",
                "lang": "en",
            },
            # game-developer.json
            {
                "id": "game-developer.json",
                "icon": "🎮",
                "title": "Game Developer",
                "subtitle": "Game Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Game Development",
                "job_tag": "Game Developer",
                "skill_tag": "Game Development",
                "lang": "en",
            },
            # javascript.json
            {
                "id": "javascript.json",
                "icon": "📜",
                "title": "JavaScript Developer",
                "subtitle": "JavaScript Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "JavaScript Developer",
                "skill_tag": "JavaScript",
                "lang": "en",
            },
            # mlops.json
            {
                "id": "mlops.json",
                "icon": "🤖",
                "title": "MLOps Engineer",
                "subtitle": "MLOps",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Machine Learning",
                "job_tag": "MLOps Engineer",
                "skill_tag": "MLOps",
                "lang": "en",
            },
            # nodejs.json
            {
                "id": "nodejs.json",
                "icon": "🟢",
                "title": "Node.js Developer",
                "subtitle": "Node.js Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "Node.js Developer",
                "skill_tag": "Node.js",
                "lang": "en",
            },
            # postgresql-dba.json
            {
                "id": "postgresql-dba.json",
                "icon": "🐘",
                "title": "PostgreSQL DBA",
                "subtitle": "Database Administration",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Database Management",
                "job_tag": "Database Administrator",
                "skill_tag": "PostgreSQL",
                "lang": "en",
            },
            # python.json
            {
                "id": "python.json",
                "icon": "🐍",
                "title": "Python Developer",
                "subtitle": "Python Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "Python Developer",
                "skill_tag": "Python",
                "lang": "en",
            },
            # qa.json
            {
                "id": "qa.json",
                "icon": "✅",
                "title": "QA Engineer",
                "subtitle": "Quality Assurance",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Testing",
                "job_tag": "QA Engineer",
                "skill_tag": "Quality Assurance",
                "lang": "en",
            },
            # react.json
            {
                "id": "react.json",
                "icon": "⚛️",
                "title": "React Developer",
                "subtitle": "React Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "React Developer",
                "skill_tag": "React",
                "lang": "en",
            },
            # server-side-game-developer.json
            {
                "id": "server-side-game-developer.json",
                "icon": "🖥️",
                "title": "Server-side Game Developer",
                "subtitle": "Game Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Game Development",
                "job_tag": "Server-side Game Developer",
                "skill_tag": "Server-side Development",
                "lang": "en",
            },
            # software-architect.json
            {
                "id": "software-architect.json",
                "icon": "🏛️",
                "title": "Software Architect",
                "subtitle": "Software Architecture",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "Software Architect",
                "skill_tag": "Architecture",
                "lang": "en",
            },
            # sql.json
            {
                "id": "sql.json",
                "icon": "🗄️",
                "title": "SQL Developer",
                "subtitle": "Database Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Database Management",
                "job_tag": "SQL Developer",
                "skill_tag": "SQL",
                "lang": "en",
            },
            # system-design.json
            {
                "id": "system-design.json",
                "icon": "🖥️",
                "title": "System Designer",
                "subtitle": "System Design",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "System Design",
                "job_tag": "System Designer",
                "skill_tag": "System Design",
                "lang": "en",
            },
            # technical-writer.json
            {
                "id": "technical-writer.json",
                "icon": "✍️",
                "title": "Technical Writer",
                "subtitle": "Technical Writing",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Technical Writing",
                "job_tag": "Technical Writer",
                "skill_tag": "Writing",
                "lang": "en",
            },
            # typescript.json
            {
                "id": "typescript.json",
                "icon": "📘",
                "title": "TypeScript Developer",
                "subtitle": "TypeScript Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "TypeScript Developer",
                "skill_tag": "TypeScript",
                "lang": "en",
            },
            # ux-design.json
            {
                "id": "ux-design.json",
                "icon": "🎨",
                "title": "UX Designer",
                "subtitle": "User Experience Design",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Design",
                "job_tag": "UX Designer",
                "skill_tag": "UX Design",
                "lang": "en",
            },
            # vue.json
            {
                "id": "vue.json",
                "icon": "🖼️",
                "title": "Vue Developer",
                "subtitle": "Vue.js Development",
                "type": "official",
                "kind": "role",
                "status": 2,
                "industry_tag": "Software Development",
                "job_tag": "Vue Developer",
                "skill_tag": "Vue.js",
                "lang": "en",
            },
        ]


        self.session.query(Roadmap).filter_by(roadmap_type='official').delete()
        self.session.commit()

        for item in items:
            with open(os.path.join(current_app.instance_path, 'roadmaps', item['id']), 'r') as f:
                mindmap = json.load(f)

            mindmap_id = mindmap.get('id', '')

            roadmap_id = item['id']
            roadmap_icon = item['icon']
            roadmap_title = item['title']
            roadmap_subtitle = item['subtitle']
            roadmap_type = item['type']
            roadmap_kind = item['kind']
            roadmap_status = item['status']
            roadmap_lang = item['lang']
            industry_tag = item['industry_tag']
            job_tag = item['job_tag']
            skill_tag = item['skill_tag']
            created_by = 'official'

            roadmap = Roadmap(
                roadmap_id=roadmap_id,
                roadmap_icon=roadmap_icon,
                roadmap_title=roadmap_title,
                roadmap_subtitle=roadmap_subtitle,
                roadmap_type=roadmap_type,
                roadmap_kind=roadmap_kind,
                roadmap_status=roadmap_status,
                roadmap_lang=roadmap_lang,
                mindmap_id=mindmap_id,
                created_by=created_by,
                industry_tag=industry_tag,
                job_tag=job_tag,
                skill_tag=skill_tag,
            )
            self.session.add(roadmap)
            self.session.commit()

            mindmap['roadmap_id'] = roadmap_id
            mindmap['created_by'] = 'official'
            mindmap['created_at'] = time.time()
            mindmap['updated_at'] = time.time()

            delete_result = delete_mindmap_nosql(current_app, mindmap_id=mindmap_id)
            current_app.logger.debug(f'nosql delete_result: {delete_result}')

            add_result = add_mindmap_nosql(current_app, mindmap)
            current_app.logger.debug(f'nosql add_result: {add_result}')

            current_app.logger.info(f'reset_official_roadmaps: {roadmap_id} {roadmap_title} {roadmap_subtitle} {roadmap_type} {roadmap_kind} {roadmap_status} {roadmap_lang} {mindmap_id}')

        return True

    def get_official_roadmaps(self, lang: str='zh_CN')->list:
        official_roadmaps = self.session.query(Roadmap).filter_by(roadmap_type='official', roadmap_status=2, roadmap_lang=lang).all()
        return [roadmap.to_dict() for roadmap in official_roadmaps]

    def get_roadmap(self, roadmap_id: str)->Roadmap:
        return self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()

    def get_roadmap_by_mindmap_id(self, mindmap_id: str)->Roadmap:
        return self.session.query(Roadmap).filter_by(mindmap_id=mindmap_id).first()

    def get_roadmaps_by_user_id(self, user_id: str, offset: int, limit: int)->list:
        return [roadmap.to_dict() for roadmap in self.session.query(Roadmap).filter_by(created_by=user_id).order_by(Roadmap.create_timestamp.desc()).offset(offset).limit(limit).all()]

    def get_roadmaps_count_by_user_id(self, user_id: str)->int:
        from sqlalchemy import func, Integer
        return self.session.query(func.cast(func.count(Roadmap.roadmap_id), Integer)).filter_by(created_by=user_id).scalar()

    def search_roadmaps_with_title_like(self, title: str, lang: str='zh_CN', offset: int=0, limit: int=10)->list:
        roadmaps = self.session.query(Roadmap).filter(Roadmap.roadmap_title.like(f'%{title}%') & (Roadmap.roadmap_status == 2) & (Roadmap.roadmap_lang == lang)).order_by(Roadmap.create_timestamp.desc()).offset(offset).limit(limit).all()
        return [roadmap.to_dict() for roadmap in roadmaps]

    def search_roadmaps_with_industry_tag_like(self, industry_tag: str, lang: str='zh_CN', offset: int=0, limit: int=10)->list:
        roadmaps = self.session.query(Roadmap).filter(Roadmap.industry_tag.like(f'%{industry_tag}%') & (Roadmap.roadmap_status == 2) & (Roadmap.roadmap_lang == lang)).order_by(Roadmap.create_timestamp.desc()).offset(offset).limit(limit).all()
        return [roadmap.to_dict() for roadmap in roadmaps]

    def search_roadmaps_with_job_tag_like(self, job_tag: str, lang: str='zh_CN', offset: int=0, limit: int=10)->list:
        roadmaps = self.session.query(Roadmap).filter(Roadmap.job_tag.like(f'%{job_tag}%') & (Roadmap.roadmap_status == 2) & (Roadmap.roadmap_lang == lang)).order_by(Roadmap.create_timestamp.desc()).offset(offset).limit(limit).all()
        return [roadmap.to_dict() for roadmap in roadmaps]

    def search_roadmaps_with_skill_tag_like(self, skill_tag: str, lang: str='zh_CN', offset: int=0, limit: int=10)->list:
        roadmaps = self.session.query(Roadmap).filter(Roadmap.skill_tag.like(f'%{skill_tag}%') & (Roadmap.roadmap_status == 2) & (Roadmap.roadmap_lang == lang)).order_by(Roadmap.create_timestamp.desc()).offset(offset).limit(limit).all()
        return [roadmap.to_dict() for roadmap in roadmaps]

    def search_roadmaps_for_topics(self, topics: list, lang: str='zh_CN', offset: int=0, limit: int=10)->list:
        from sqlalchemy import or_

        query_filters = []
        for topic in topics:
            query_filters.append(
                (Roadmap.roadmap_title.like(f'%{topic}%') |
                Roadmap.industry_tag.like(f'%{topic}%') |
                Roadmap.job_tag.like(f'%{topic}%') |
                Roadmap.skill_tag.like(f'%{topic}%'))
            )

        roadmaps = self.session.query(Roadmap).filter(
            or_(*query_filters) & (Roadmap.roadmap_status == 2) & (Roadmap.roadmap_lang == lang)
        ).distinct().order_by(Roadmap.create_timestamp.desc()).offset(offset).limit(limit).all()
        return [roadmap.to_dict() for roadmap in roadmaps]

    def all_industry_tags(self, lang: str='zh_CN')->list:
        industry_tags = self.session.query(Roadmap.industry_tag).distinct().filter(Roadmap.roadmap_lang == lang).all()
        return [industry_tag[0] for industry_tag in industry_tags if industry_tag[0] is not None]

    def job_tags_of_industry_tag(self, industry_tag: str, lang: str='zh_CN')->list:
        job_tags = self.session.query(Roadmap.job_tag).filter(Roadmap.industry_tag == industry_tag).distinct().filter(Roadmap.roadmap_lang == lang).all()
        return [job_tag[0] for job_tag in job_tags if job_tag[0] is not None]

    def skill_tags_of_job_tag(self, job_tag: str, lang: str='zh_CN')->list:
        skill_tags = self.session.query(Roadmap.skill_tag).filter(Roadmap.job_tag == job_tag).distinct().filter(Roadmap.roadmap_lang == lang).all()
        return [skill_tag[0] for skill_tag in skill_tags if skill_tag[0] is not None]

    def get_public_roadmaps(self, lang: str='zh_CN')->list:
        public_roadmaps = self.session.query(Roadmap).filter_by(roadmap_status=2, roadmap_lang=lang).all()
        return [roadmap.to_dict() for roadmap in public_roadmaps]

    def set_roadmap_public(self, roadmap_id: str)->bool:
        roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
        if roadmap:
            roadmap.roadmap_status = RoadmapStatus.PUBLIC.value
            self.session.commit()
        return True

    def set_roadmap_private(self, roadmap_id: str)->bool:
        roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
        if roadmap:
            roadmap.roadmap_status = RoadmapStatus.PRIVATE.value
            self.session.commit()
        return True

    def get_all_roadmaps(self, lang: str='zh_CN')->list:
        roadmaps = self.session.query(Roadmap).filter(Roadmap.roadmap_lang == lang).all()
        return [roadmap.to_dict() for roadmap in roadmaps]

    def delete_roadmap(self, roadmap_id: str)->bool:
        roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
        if roadmap:
            self.session.delete(roadmap)
            self.session.commit()
        return True

    def get_hot_roadmaps(self, roadmap_kind: str, order_by: str, lang: str='zh_CN', offset: int=0, limit: int=10)->list:
        if order_by == 'viewed':
            order_by_field = Roadmap.viewed
        elif order_by == 'participanted':
            order_by_field = Roadmap.participanted
        elif order_by == 'completed':
            order_by_field = Roadmap.completed
        elif order_by == 'favorited':
            order_by_field = Roadmap.favorited
        elif order_by == 'shared':
            order_by_field = Roadmap.shared
        else:
            order_by_field = Roadmap.create_timestamp

        roadmaps = self.session.query(Roadmap).filter_by(roadmap_kind=roadmap_kind, roadmap_lang=lang).order_by(order_by_field.desc(), Roadmap.create_timestamp.desc()).offset(offset).limit(limit).all()
        return [roadmap.to_dict() for roadmap in roadmaps]

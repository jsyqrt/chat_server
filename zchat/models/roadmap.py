import json
import uuid
import time
from enum import Enum

from flask import current_app, url_for

from zchat.db import db
from zchat.rand import *
from zchat.meili import *

class Roadmap(db.Model):
    __tablename__ = 'ROADMAP'

    roadmap_id = db.Column(db.String, primary_key=True)
    roadmap_icon = db.Column(db.String, nullable=False)
    roadmap_title = db.Column(db.String, nullable=False)
    roadmap_subtitle = db.Column(db.String, nullable=False)
    roadmap_type = db.Column(db.String, nullable=False) # official, user
    roadmap_kind = db.Column(db.String, nullable=False) # role, skill, concept
    roadmap_status = db.Column(db.Integer, nullable=False, default=0) # 0->create, 1->verified, 2->public
    mindmap_id = db.Column(db.String, nullable=False)
    created_by = db.Column(db.String, nullable=True)

    create_timestamp = db.Column(db.REAL, nullable=True, default=time.time())
    update_timestamp = db.Column(db.REAL, nullable=True, default=time.time())

    __table_args__ = (
        db.Index('index_ROADMAP_title', 'roadmap_title', unique=False),
        db.Index('index_ROADMAP_subtitle', 'roadmap_subtitle', unique=False),
        db.Index('index_ROADMAP_type', 'roadmap_type', unique=False),
        db.Index('index_ROADMAP_kind', 'roadmap_kind', unique=False),
        db.Index('index_ROADMAP_type', 'roadmap_type', unique=False),
        db.Index('index_ROADMAP_mindmap_id', 'mindmap_id', unique=False),
        db.Index('index_ROADMAP_create_timestamp', 'create_timestamp', unique=False),
        db.Index('index_ROADMAP_update_timestamp', 'update_timestamp', unique=False),
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
            'mindmap_id': self.mindmap_id,
            'create_timestamp': self.create_timestamp,
            'update_timestamp': self.update_timestamp,
        }

class RoadmapInteraction(db.Model):
    __tablename__ = 'ROADMAP_INTERACTION'

    roadmap_id = db.Column(db.String, primary_key=True)
    user_id = db.Column(db.String, nullable=False)

    participanted = db.Column(db.Integer, nullable=False, default=0)
    completed = db.Column(db.Integer, nullable=False, default=0)
    favorited = db.Column(db.Integer, nullable=False, default=0)
    shared = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.Index('index_ROADMAP_INTERACTION_user_id', 'user_id', unique=False),
        db.Index('index_ROADMAP_INTERACTION_participanted', 'participanted', unique=False),
        db.Index('index_ROADMAP_INTERACTION_completed', 'completed', unique=False),
        db.Index('index_ROADMAP_INTERACTION_favorited', 'favorited', unique=False),
        db.Index('index_ROADMAP_INTERACTION_shared', 'shared', unique=False),
    )

    def to_dict(self):
        return {
            'roadmap_id': self.roadmap_id,
            'user_id': self.user_id,
            'participanted': self.participanted,
            'completed': self.completed,
            'favorited': self.favorited,
            'shared': self.shared,
        }

class RoadmapInteractionOps:
    def __init__(self, session):
        self.session = session

    def participant(self, roadmap_id: str, user_id: str)->bool:
        interaction = self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, user_id=user_id).first()
        if interaction:
            if interaction.participanted == 0:
                interaction.participanted = 1
                self.session.commit()
                return True
        else:
            interaction = RoadmapInteraction(roadmap_id=roadmap_id, user_id=user_id, participanted=1)
            self.session.add(interaction)
            self.session.commit()
            return True

    def completion(self, roadmap_id: str, user_id: str)->bool:
        interaction = self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, user_id=user_id).first()
        if interaction:
            if interaction.completed == 0:
                interaction.participanted = 1
                interaction.completed = 1
                self.session.commit()
                return True
        else:
            interaction = RoadmapInteraction(roadmap_id=roadmap_id, user_id=user_id, participanted=1, completed=1)
            self.session.add(interaction)
            self.session.commit()
            return True

    def favorite(self, roadmap_id: str, user_id: str)->bool:
        interaction = self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, user_id=user_id).first()
        if interaction:
            if interaction.favorited == 0:
                interaction.favorited = 1
                self.session.commit()
                return True
        else:
            interaction = RoadmapInteraction(roadmap_id=roadmap_id, user_id=user_id, favorited=1)
            self.session.add(interaction)
            self.session.commit()
            return True

    def un_favorite(self, roadmap_id: str, user_id: str)->bool:
        interaction = self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, user_id=user_id).first()
        if interaction:
            interaction.favorited = 0
            self.session.commit()
            return True
        return False

    def share(self, roadmap_id: str, user_id: str)->bool:
        interaction = self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, user_id=user_id).first()
        if interaction:
            interaction.shared += 1
            self.session.commit()
            return True
        else:
            interaction = RoadmapInteraction(roadmap_id=roadmap_id, user_id=user_id, shared=1)
            self.session.add(interaction)
            self.session.commit()
            return True

    def get_stats(self, roadmap_id: str)->dict:
        from sqlalchemy import func

        participant_count = self.session.query(func.sum(RoadmapInteraction.participanted)).filter_by(roadmap_id=roadmap_id).scalar() or 0
        completion_count = self.session.query(func.sum(RoadmapInteraction.completed)).filter_by(roadmap_id=roadmap_id).scalar() or 0
        favorite_count = self.session.query(func.sum(RoadmapInteraction.favorited)).filter_by(roadmap_id=roadmap_id).scalar() or 0
        share_count = self.session.query(func.sum(RoadmapInteraction.shared)).filter_by(roadmap_id=roadmap_id).scalar() or 0

        return {
            'participants': participant_count,
            'completions': completion_count,
            'favorites': favorite_count,
            'shares': share_count,
        }

class RoadmapOps:
    def __init__(self, session):
        self.session = session

    def create_roadmap(self, id, icon, title, subtitle, type, kind, status, mindmap_id, created_by)->Roadmap:
        try:
            roadmap = Roadmap(
                roadmap_id=id,
                roadmap_icon=icon,
                roadmap_title=title,
                roadmap_subtitle=subtitle,
                roadmap_type=type,
                roadmap_kind=kind,
                roadmap_status=status,
                mindmap_id=mindmap_id,
                created_by=created_by,
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
                "id": "nodejs.json",
                "icon": "⚡",
                "title": "Node.js编程",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
            },
            # devops.json
            {
                "id": "devops.json",
                "icon": "🔄",
                "title": "DevOps工程师",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "role",
                "status": 2,
            },
            # server-side-game-developer.json
            {
                "id": "server-side-game-developer.json",
                "icon": "🎮",
                "title": "服务器端游戏开发",
                "subtitle": "游戏开发",
                "type": "official",
                "kind": "role",
                "status": 2,
            },
            # frontend.json
            {
                "id": "frontend.json",
                "icon": "🖥️",
                "title": "前端开发",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "role",
                "status": 2,
            },
            # computer-science.json
            {
                "id": "computer-science.json",
                "icon": "🧠",
                "title": "计算机科学",
                "subtitle": "基础知识",
                "type": "official",
                "kind": "concept",
                "status": 2,
            },
            # python.json
            {
                "id": "python.json",
                "icon": "🐍",
                "title": "Python开发",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
            },
            # software-architect.json
            {
                "id": "software-architect.json",
                "icon": "🏗️",
                "title": "软件架构师",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "role",
                "status": 2,
            },
            # data-analyst.json
            {
                "id": "data-analyst.json",
                "icon": "📊",
                "title": "数据分析师",
                "subtitle": "数据科学",
                "type": "official",
                "kind": "role",
                "status": 2,
            },
            # typescript.json
            {
                "id": "typescript.json",
                "icon": "📘",
                "title": "TypeScript编程",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
            },
            # mlops.json
            {
                "id": "mlops.json",
                "icon": "🤖",
                "title": "MLOps工程师",
                "subtitle": "机器学习",
                "type": "official",
                "kind": "role",
                "status": 2,
            },
            # vue.json
            {
                "id": "vue.json",
                "icon": "🟢",
                "title": "Vue开发",
                "subtitle": "前端开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
            },
            # aspnet-core.json
            {
                "id": "aspnet-core.json",
                "icon": "🌐",
                "title": "ASP.NET Core开发",
                "subtitle": "后端开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
            },
            # postgresql-dba.json
            {
                "id": "postgresql-dba.json",
                "icon": "🐘",
                "title": "PostgreSQL数据库管理",
                "subtitle": "数据库",
                "type": "official",
                "kind": "skill",
                "status": 2,
            },
            # angular.json
            {
                "id": "angular.json",
                "icon": "🔺",
                "title": "Angular开发",
                "subtitle": "前端开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
            },
            # qa.json
            {
                "id": "qa.json",
                "icon": "🔍",
                "title": "QA测试工程师",
                "subtitle": "软件测试",
                "type": "official",
                "kind": "role",
                "status": 2,
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
            },
            # backend.json
            {
                "id": "backend.json",
                "icon": "⚙️",
                "title": "Backend Engineer",
                "subtitle": "Software Development",
                "type": "official",
                "kind": "role",
                "status": 2,
            },
            # cyber-security.json
            {
                "id": "cyber-security.json",
                "icon": "🔒",
                "title": "网络安全",
                "subtitle": "安全",
                "type": "official",
                "kind": "role",
                "status": 2,
            },
            # blockchain.json
            {
                "id": "blockchain.json",
                "icon": "⛓️",
                "title": "区块链开发",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "role",
                "status": 2,
            },
            # full-stack.json
            {
                "id": "full-stack.json",
                "icon": "🧰",
                "title": "全栈开发",
                "subtitle": "软件开发",
                "type": "official",
                "kind": "role",
                "status": 2,
            },
            # android.json
            {
                "id": "android.json",
                "icon": "📱",
                "title": "Android开发",
                "subtitle": "移动开发",
                "type": "official",
                "kind": "role",
                "status": 2,
            },
            # system-design.json
            {
                "id": "system-design.json",
                "icon": "📐",
                "title": "系统设计",
                "subtitle": "软件架构",
                "type": "official",
                "kind": "skill",
                "status": 2,
            },
            # javascript.json
            {
                "id": "javascript.json",
                "icon": "💛",
                "title": "JavaScript编程",
                "subtitle": "前端开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
            },
            # technical-writer.json
            {
                "id": "technical-writer.json",
                "icon": "📝",
                "title": "技术文档写作",
                "subtitle": "技术写作",
                "type": "official",
                "kind": "skill",
                "status": 2,
            },
            # game-developer.json
            {
                "id": "game-developer.json",
                "icon": "🎲",
                "title": "游戏开发",
                "subtitle": "游戏开发",
                "type": "official",
                "kind": "role",
                "status": 2,
            },
            # react.json
            {
                "id": "react.json",
                "icon": "⚛️",
                "title": "React开发",
                "subtitle": "前端开发",
                "type": "official",
                "kind": "skill",
                "status": 2,
            },
            # ux-design.json
            {
                "id": "ux-design.json",
                "icon": "🎨",
                "title": "UX设计",
                "subtitle": "设计",
                "type": "official",
                "kind": "role",
                "status": 2,
            },
            # sql.json
            {
                "id": "sql.json",
                "icon": "🗃️",
                "title": "SQL数据库",
                "subtitle": "数据库",
                "type": "official",
                "kind": "skill",
                "status": 2,
            },
        ]

        for item in items:
            with open(os.path.join(current_app.instance_path, item['id']), 'r') as f:
                mindmap = json.load(f)

            mindmap_id = mindmap.get('id', '')

            roadmap_id = item['id']
            roadmap_icon = item['icon']
            roadmap_title = item['title']
            roadmap_subtitle = item['subtitle']
            roadmap_type = item['type']
            roadmap_kind = item['kind']
            roadmap_status = item['status']
            created_by = 'official'

            if self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first():
                self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).delete()

            roadmap = Roadmap(
                roadmap_id=roadmap_id,
                roadmap_icon=roadmap_icon,
                roadmap_title=roadmap_title,
                roadmap_subtitle=roadmap_subtitle,
                roadmap_type=roadmap_type,
                roadmap_kind=roadmap_kind,
                roadmap_status=roadmap_status,
                mindmap_id=mindmap_id,
                created_by=created_by,
            )
            self.session.add(roadmap)
            self.session.commit()

            mindmap['roadmap_id'] = roadmap_id
            mindmap['created_by'] = 'official'
            mindmap['created_at'] = time.time()
            mindmap['updated_at'] = time.time()

            delete_result = delete_mindmap_from_meili(current_app, mindmap_id=mindmap_id)
            current_app.logger.debug(f'meili delete_result: {add_result}')

            add_result = add_mindmap_to_meili(current_app, mindmap)
            current_app.logger.debug(f'meili add_result: {add_result}')

            current_app.logger.info(f'reset_official_roadmaps: {roadmap_id} {roadmap_title} {roadmap_subtitle} {roadmap_type} {roadmap_kind} {roadmap_status} {mindmap_id}')

        return True

    def get_official_roadmaps(self)->list:
        official_roadmaps = self.session.query(Roadmap).filter_by(roadmap_type='official', roadmap_status=2).all()
        return [roadmap.to_dict() for roadmap in official_roadmaps]

    def get_roadmap(self, roadmap_id: str)->Roadmap:
        return self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()

    def get_roadmap_by_mindmap_id(self, mindmap_id: str)->Roadmap:
        return self.session.query(Roadmap).filter_by(mindmap_id=mindmap_id).first()

    def get_public_roadmaps(self)->list:
        public_roadmaps = self.session.query(Roadmap).filter_by(roadmap_status=2).all()
        return [roadmap.to_dict() for roadmap in public_roadmaps]

    def verify_roadmap(self, roadmap_id: str)->bool:
        roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
        if roadmap:
            roadmap.roadmap_status = 1
            self.session.commit()
        return True

    def publish_roadmap(self, roadmap_id: str)->bool:
        roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
        if roadmap:
            roadmap.roadmap_status = 2
            self.session.commit()
        return True

    def private_roadmap(self, roadmap_id: str)->bool:
        roadmap = self.session.query(Roadmap).filter_by(roadmap_id=roadmap_id).first()
        if roadmap:
            roadmap.roadmap_status = 0
            self.session.commit()
        return True

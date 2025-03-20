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
    industry_tag = db.Column(db.String, nullable=True)
    job_tag = db.Column(db.String, nullable=True)
    skill_tag = db.Column(db.String, nullable=True)

    create_timestamp = db.Column(db.REAL, nullable=True, default=time.time())
    update_timestamp = db.Column(db.REAL, nullable=True, default=time.time())

    __table_args__ = (
        db.Index('index_ROADMAP_title', 'roadmap_title', unique=False),
        db.Index('index_ROADMAP_subtitle', 'roadmap_subtitle', unique=False),
        db.Index('index_ROADMAP_type', 'roadmap_type', unique=False),
        db.Index('index_ROADMAP_kind', 'roadmap_kind', unique=False),
        db.Index('index_ROADMAP_type', 'roadmap_type', unique=False),
        db.Index('index_ROADMAP_mindmap_id', 'mindmap_id', unique=False),
        db.Index('index_ROADMAP_industry_tag', 'industry_tag', unique=False),
        db.Index('index_ROADMAP_job_tag', 'job_tag', unique=False),
        db.Index('index_ROADMAP_skill_tag', 'skill_tag', unique=False),
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
            'industry_tag': self.industry_tag,
            'job_tag': self.job_tag,
            'skill_tag': self.skill_tag,
            'created_at': self.create_timestamp,
            'updated_at': self.update_timestamp,
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

    def get_participants_count_of_roadmap(self, roadmap_id: str)->int:
        return self.session.query(RoadmapInteraction).filter_by(roadmap_id=roadmap_id, participanted=1).count()

    def get_participants_count_of_user(self, user_id: str)->int:
        return self.session.query(RoadmapInteraction).filter_by(user_id=user_id, participanted=1).count()

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

    def get_favorites(self, user_id: str)->list:
        interactions = self.session.query(RoadmapInteraction).filter_by(user_id=user_id).all()
        return [interaction.roadmap_id for interaction in interactions if interaction.favorited == 1]

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

    def create_roadmap(self, id, icon, title, subtitle, type, kind, status, mindmap_id, created_by, industry_tag, job_tag, skill_tag)->Roadmap:
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
            },
        ]

        self.session.query(Roadmap).filter_by(roadmap_type='official').delete()
        self.session.commit()

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

            delete_result = delete_mindmap_from_meili(current_app, mindmap_id=mindmap_id)
            current_app.logger.debug(f'meili delete_result: {delete_result}')

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

    def get_roadmaps_by_user_id(self, user_id: str, offset: int, limit: int)->list:
        return [roadmap.to_dict() for roadmap in self.session.query(Roadmap).filter_by(created_by=user_id).order_by(Roadmap.create_timestamp.desc()).offset(offset).limit(limit).all()]

    def get_roadmaps_count_by_user_id(self, user_id: str)->int:
        return self.session.query(Roadmap).filter_by(created_by=user_id).count()

    def search_roadmaps_with_title_like(self, title: str)->list:
        roadmaps = self.session.query(Roadmap).filter(Roadmap.roadmap_title.like(f'%{title}%')).all()
        return [roadmap.to_dict() for roadmap in roadmaps]

    def search_roadmaps_with_industry_tag_like(self, industry_tag: str)->list:
        roadmaps = self.session.query(Roadmap).filter(Roadmap.industry_tag.like(f'%{industry_tag}%')).all()
        return [roadmap.to_dict() for roadmap in roadmaps]

    def search_roadmaps_with_job_tag_like(self, job_tag: str)->list:
        roadmaps = self.session.query(Roadmap).filter(Roadmap.job_tag.like(f'%{job_tag}%')).all()
        return [roadmap.to_dict() for roadmap in roadmaps]

    def search_roadmaps_with_skill_tag_like(self, skill_tag: str)->list:
        roadmaps = self.session.query(Roadmap).filter(Roadmap.skill_tag.like(f'%{skill_tag}%')).all()
        return [roadmap.to_dict() for roadmap in roadmaps]

    def search_roadmaps_for_topic(self, topic, roadmap_type, limit: int=10)->list:
        roadmaps = self.session.query(Roadmap).filter(
            Roadmap.roadmap_type == roadmap_type,
            (Roadmap.roadmap_title.like(f'%{topic}%') |
            Roadmap.industry_tag.like(f'%{topic}%') |
            Roadmap.job_tag.like(f'%{topic}%') |
            Roadmap.skill_tag.like(f'%{topic}%'))
        ).distinct().limit(limit).all()
        return [roadmap.to_dict() for roadmap in roadmaps]

    def all_industry_tags(self)->list:
        industry_tags = self.session.query(Roadmap.industry_tag).distinct().all()
        return [industry_tag[0] for industry_tag in industry_tags if industry_tag[0] is not None]

    def job_tags_of_industry_tag(self, industry_tag: str)->list:
        job_tags = self.session.query(Roadmap.job_tag).filter(Roadmap.industry_tag == industry_tag).distinct().all()
        return [job_tag[0] for job_tag in job_tags if job_tag[0] is not None]

    def skill_tags_of_job_tag(self, job_tag: str)->list:
        skill_tags = self.session.query(Roadmap.skill_tag).filter(Roadmap.job_tag == job_tag).distinct().all()
        return [skill_tag[0] for skill_tag in skill_tags if skill_tag[0] is not None]

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

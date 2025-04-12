# Import all models to ensure they're registered with SQLAlchemy
# This is important for Flask-Migrate to detect and migrate all models

# First import the db instance
from zchat.models.base import db

# Make sure we explicitly import all model classes
try:
    from zchat.models.user import User, AdminUser
    from zchat.models.chat import ChatSession, ChatMessage
    from zchat.models.points import PointsTransaction, PointsBalance
    from zchat.models.roadmap import Roadmap, RoadmapInteraction
    from zchat.models.invitation import Invitation
    from zchat.models.subscription import Subscription

except ImportError as e:
    import sys
    print(f"Error importing models: {e}", file=sys.stderr)
    raise e

# Export all models
__all__ = [
    'db',
    'User', 'AdminUser',
    'ChatSession', 'ChatMessage',
    'PointsTransaction', 'PointsBalance',
    'Roadmap', 'RoadmapInteraction',
    'Invitation',
    'Subscription'
]

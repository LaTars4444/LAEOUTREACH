from datetime import datetime, timedelta

def check_access(user, feature):
    """
    feature: 'email' (24h trial) or 'ai' (48h trial)
    Returns: Boolean
    """
    if not user:
        return False

    # 1. Check Paid Status
    if user.subscription_status == 'lifetime':
        return True
    
    if user.subscription_status == 'weekly':
        if user.subscription_end and user.subscription_end > datetime.utcnow():
            return True

    # 2. Check Strict Time-Based Trials
    now = datetime.utcnow()
    trial_start = user.created_at
    
    if feature == 'email':
        # 24 Hour Trial
        if now < trial_start + timedelta(hours=24):
            return True
            
    elif feature == 'ai':
        # 48 Hour Trial
        if now < trial_start + timedelta(hours=48):
            return True

    return False

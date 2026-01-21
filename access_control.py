from datetime import datetime, timedelta

def check_access(user, feature):
    """
    feature: 'email' (24h trial) or 'ai' (48h trial)
    Returns: Boolean (True if access allowed)
    """
    if not user:
        return False

    # 1. Check Paid Status (Permanent Unlock)
    if user.subscription_status == 'lifetime':
        return True
    
    # 2. Check Subscription Status
    if user.subscription_status == 'weekly':
        if user.subscription_end and user.subscription_end > datetime.utcnow():
            return True

    # 3. Check Trial Status
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

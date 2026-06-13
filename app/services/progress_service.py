def calculate_level(points: int) -> str:
    """Calculates user level based on total points, returning a developer version (V1-V5)."""
    if points <= 100: return "V1"
    if points <= 300: return "V2"
    if points <= 700: return "V3"
    if points <= 1500: return "V4"
    return "V5"

def get_user_progress(supabase, user_id: str):
    """Fetches the current user progress record."""
    response = supabase.table('user_progress')\
        .select('*')\
        .eq('user_id', user_id)\
        .maybe_single()\
        .execute()
    return getattr(response, 'data', None)

def get_leaderboard(supabase, limit: int = 50):
    """Fetches the top users ranked by points."""
    response = supabase.table('user_progress')\
        .select('*, profiles(display_name, avatar_url)')\
        .order('points', desc=True)\
        .order('solved_challenges', desc=True)\
        .limit(limit)\
        .execute()
    return getattr(response, 'data', [])

def get_user_rank(supabase, points: int) -> int:
    """Calculates user rank based on points."""
    response = supabase.table('user_progress')\
        .select('user_id', count='exact')\
        .gt('points', points)\
        .execute()
    return (getattr(response, 'count', 0) or 0) + 1

def increment_user_progress(supabase, user_id: str, points_to_add: int):
    """
    Awards points to a user and increments their solved challenge count.
    Updates or creates the user_progress record.
    """
    current = get_user_progress(supabase, user_id)
    
    if not current:
        current = {
            "user_id": user_id, 
            "points": 0, 
            "solved_challenges": 0, 
            "approved_submissions": 0
        }
        
    new_points = current.get('points', 0) + points_to_add
    new_solved = current.get('solved_challenges', 0) + 1
    new_approved = current.get('approved_submissions', 0) + 1
    new_level = calculate_level(new_points)
    
    upsert_data = {
        'user_id': user_id,
        'points': new_points,
        'level': new_level,
        'solved_challenges': new_solved,
        'approved_submissions': new_approved,
        'updated_at': "now()"
    }
    
    result = supabase.table('user_progress').upsert(upsert_data).execute()
        
    return getattr(result, 'data', [None])[0] if getattr(result, 'data', None) else None

from ..tools import tool
from config.secrets import LINKEDIN_EMAIL, LINKEDIN_PASSWORD
from linkedin_client import get_linkedin_client
from typing import List, Dict, Optional, Literal
import json

# Initialize LinkedIn client
linkedin_client = get_linkedin_client(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)

@tool(
    description="Search for LinkedIn profiles with various filters. This tool provides comprehensive search functionality for finding people on LinkedIn. It supports filtering by keywords, companies, regions, industries, schools, and more.",
    keywords="Optional search keywords to find in profiles",
    current_company="Optional list of company URN IDs to filter by current company",
    past_companies="Optional list of company URN IDs to filter by past companies",
    regions="Optional list of geo URN IDs to filter by location",
    industries="Optional list of industry URN IDs to filter by industry",
    schools="Optional list of school URN IDs to filter by education",
    profile_languages="Optional list of 2-letter language codes to filter by profile language",
    network_depths="Optional list of connection degrees ('F' for 1st, 'S' for 2nd, 'O' for 3rd+)",
    include_private_profiles="Whether to include private profiles in search results",
    limit="Maximum number of results to return, defaults to 100",
    safe=True
)
def search_people(
    keywords: str = None,
    current_company: List[str] = None,
    past_companies: List[str] = None,
    regions: List[str] = None,
    industries: List[str] = None,
    schools: List[str] = None,
    profile_languages: List[str] = None,
    network_depths: List[Literal["F", "S", "O"]] = None,
    include_private_profiles: bool = False,
    limit: int = 100
) -> str:
    """Search for LinkedIn profiles with various filters"""
    results = linkedin_client.search_people(
        keywords=keywords,
        current_company=current_company,
        past_companies=past_companies,
        regions=regions,
        industries=industries,
        schools=schools,
        profile_languages=profile_languages,
        network_depths=network_depths,
        include_private_profiles=include_private_profiles
    )
    return json.dumps(results[:limit] if limit > 0 else results)

@tool(
    description="Get detailed information about a LinkedIn profile. This includes work experience, education, skills, and other public profile information. You must provide either a public_id or urn_id.",
    public_id="The public identifier of the LinkedIn profile (e.g., 'john-doe-123')",
    urn_id="The URN identifier of the LinkedIn profile (e.g., 'urn:li:fs_miniProfile:AbC123')",
    safe=True
)
def get_profile(
    public_id: str = None,
    urn_id: str = None
) -> str:
    """Get detailed profile information for a LinkedIn user"""
    profile = linkedin_client.get_profile(
        public_id=public_id,
        urn_id=urn_id
    )
    try:
        return json.dumps(profile)
    except Exception as e:
        raise ValueError(f"Could not serialize profile data to JSON. Raw data: {profile}. Error: {str(e)}")

@tool(
    description="Get contact information for a LinkedIn profile. This includes email, phone, websites, and other contact details if available. You must provide either a public_id or urn_id.",
    public_id="The public identifier of the LinkedIn profile",
    urn_id="The URN identifier of the LinkedIn profile",
    safe=True
)
def get_profile_contact_info(
    public_id: str = None,
    urn_id: str = None
) -> str:
    """Get contact information for a LinkedIn profile"""
    contact_info = linkedin_client.get_profile_contact_info(
        public_id=public_id,
        urn_id=urn_id
    )
    return json.dumps(contact_info)

@tool(
    description="Send a connection request to a LinkedIn profile. Optionally include a personalized message with the request.",
    profile_public_id="The public identifier of the LinkedIn profile to connect with",
    message="Optional personalized message to send with the connection request",
    safe=False
)
def add_connection(
    profile_public_id: str,
    message: str = ""
) -> str:
    """Send a connection request to a LinkedIn profile"""
    result = linkedin_client.add_connection(
        profile_public_id=profile_public_id,
        message=message
    )
    return json.dumps({"success": not result})

@tool(
    description="Remove an existing connection with a LinkedIn profile.",
    public_profile_id="The public identifier of the LinkedIn profile to disconnect from",
    safe=False
)
def remove_connection(
    public_profile_id: str
) -> str:
    """Remove a connection with a LinkedIn profile"""
    result = linkedin_client.remove_connection(public_profile_id)
    return json.dumps({"success": not result})

@tool(
    description="Search for jobs on LinkedIn with various filters. Supports filtering by keywords, companies, experience level, job type, location, and more.",
    keywords="Search keywords for the job search",
    companies="Optional list of company URN IDs to filter by",
    experience="Optional list of experience levels (1=internship, 2=entry, 3=associate, 4=mid-senior, 5=director, 6=executive)",
    job_type="Optional list of job types (F=full-time, C=contract, P=part-time, T=temporary, I=internship, V=volunteer, O=other)",
    location_name="Optional location name to search within (e.g., 'San Francisco, CA')",
    remote="Optional list of remote work options (1=onsite, 2=remote, 3=hybrid)",
    listed_at="Maximum age of job postings in seconds (default 86400 for 24 hours)",
    distance="Maximum distance from location in miles",
    limit="Maximum number of results to return",
    safe=True
)
def search_jobs(
    keywords: str = None,
    companies: List[str] = None,
    experience: List[Literal["1", "2", "3", "4", "5", "6"]] = None,
    job_type: List[Literal["F", "C", "P", "T", "I", "V", "O"]] = None,
    location_name: str = None,
    remote: List[Literal["1", "2", "3"]] = None,
    listed_at: int = 86400,
    distance: int = None,
    limit: int = 100
) -> str:
    """Search for jobs on LinkedIn"""
    results = linkedin_client.search_jobs(
        keywords=keywords,
        companies=companies,
        experience=experience,
        job_type=job_type,
        location_name=location_name,
        remote=remote,
        listed_at=listed_at,
        distance=distance
    )
    return json.dumps(results[:limit] if limit > 0 else results)

@tool(
    description="Get detailed information about a specific job posting on LinkedIn.",
    job_id="The LinkedIn job ID to get details for",
    safe=True
)
def get_job(
    job_id: str
) -> str:
    """Get detailed information about a job posting"""
    job = linkedin_client.get_job(job_id)
    return json.dumps(job)

@tool(
    description="Send a message to LinkedIn connections. You must provide either a conversation_urn_id for an existing conversation or a list of recipient URNs for a new conversation.",
    message_body="The message text to send",
    conversation_urn_id="URN ID of an existing conversation",
    recipients="List of profile URN IDs for new conversation",
    safe=False
)
def send_message(
    message_body: str,
    conversation_urn_id: str = None,
    recipients: List[str] = None
) -> str:
    """Send a message to LinkedIn connections"""
    result = linkedin_client.send_message(
        message_body=message_body,
        conversation_urn_id=conversation_urn_id,
        recipients=recipients
    )
    return json.dumps({"success": not result})

@tool(
    description="Get a list of all conversations (message threads) the user is participating in.",
    safe=True
)
def get_conversations() -> str:
    """Get list of user's conversations"""
    conversations = linkedin_client.get_conversations()
    return json.dumps(conversations)

@tool(
    description="Get detailed information about a specific conversation, including messages and participants.",
    conversation_urn_id="The URN ID of the conversation to fetch",
    safe=True
)
def get_conversation(
    conversation_urn_id: str
) -> str:
    """Get details of a specific conversation"""
    conversation = linkedin_client.get_conversation(conversation_urn_id)
    return json.dumps(conversation)

@tool(
    description="Search for companies on LinkedIn. Supports searching by keywords and various filters.",
    keywords="List of keywords to search for",
    safe=True
)
def search_companies(
    keywords: List[str] = None
) -> str:
    """Search for companies on LinkedIn"""
    companies = linkedin_client.search_companies(keywords=keywords)
    return json.dumps(companies)

@tool(
    description="Get detailed information about a specific company on LinkedIn.",
    public_id="The public identifier of the company to get details for",
    safe=True
)
def get_company(
    public_id: str
) -> str:
    """Get detailed information about a company"""
    company = linkedin_client.get_company(public_id)
    return json.dumps(company)

@tool(
    description="Get a list of skills for a LinkedIn profile. Returns the skills listed on the profile, including endorsements if available. You must provide either a public_id or urn_id.",
    public_id="The public identifier of the LinkedIn profile",
    urn_id="The URN identifier of the LinkedIn profile",
    safe=True
)
def get_profile_skills(
    public_id: str = None,
    urn_id: str = None
) -> str:
    """Get skills listed on a LinkedIn profile"""
    skills = linkedin_client.get_profile_skills(
        public_id=public_id,
        urn_id=urn_id
    )
    return json.dumps(skills)

@tool(
    description="Get a list of posts made by a LinkedIn profile. Returns recent posts with their content and engagement metrics. You must provide either a public_id or urn_id.",
    public_id="The public identifier of the LinkedIn profile",
    urn_id="The URN identifier of the LinkedIn profile",
    post_count="Number of posts to fetch (default 10)",
    safe=True
)
def get_profile_posts(
    public_id: str = None,
    urn_id: str = None,
    post_count: int = 10
) -> str:
    """Get posts from a LinkedIn profile"""
    posts = linkedin_client.get_profile_posts(
        public_id=public_id,
        urn_id=urn_id,
        post_count=post_count
    )
    return json.dumps(posts)

@tool(
    description="Get comments on a specific LinkedIn post.",
    post_urn="The URN identifier of the post",
    comment_count="Maximum number of comments to fetch (default 100)",
    safe=True
)
def get_post_comments(
    post_urn: str,
    comment_count: int = 100
) -> str:
    """Get comments on a LinkedIn post"""
    comments = linkedin_client.get_post_comments(
        post_urn=post_urn,
        comment_count=comment_count
    )
    return json.dumps(comments)

@tool(
    description="Get reactions (likes, etc.) on a specific LinkedIn post.",
    urn_id="The URN identifier of the post",
    max_results="Maximum number of reactions to fetch",
    safe=True
)
def get_post_reactions(
    urn_id: str,
    max_results: int = None
) -> str:
    """Get reactions on a LinkedIn post"""
    reactions = linkedin_client.get_post_reactions(
        urn_id=urn_id,
        max_results=max_results
    )
    return json.dumps(reactions)

@tool(
    description="React to a LinkedIn post with a specific reaction type.",
    post_urn_id="The URN identifier of the post",
    reaction_type="Type of reaction (LIKE, PRAISE, APPRECIATION, EMPATHY, INTEREST, ENTERTAINMENT)",
    safe=False
)
def react_to_post(
    post_urn_id: str,
    reaction_type: Literal["LIKE", "PRAISE", "APPRECIATION", "EMPATHY", "INTEREST", "ENTERTAINMENT"] = "LIKE"
) -> str:
    """React to a LinkedIn post"""
    result = linkedin_client.react_to_post(
        post_urn_id=post_urn_id,
        reaction_type=reaction_type
    )
    return json.dumps({"success": not result})

@tool(
    description="Get a list of connection invitations for the current user.",
    start="Index to start fetching invitations from",
    limit="Maximum number of invitations to fetch",
    safe=True
)
def get_invitations(
    start: int = 0,
    limit: int = 3
) -> str:
    """Get connection invitations"""
    invitations = linkedin_client.get_invitations(
        start=start,
        limit=limit
    )
    return json.dumps(invitations)

@tool(
    description="Accept or reject a connection invitation.",
    invitation_entity_urn="URN identifier of the invitation",
    invitation_shared_secret="Shared secret of the invitation",
    action="Whether to accept or reject the invitation",
    safe=False
)
def reply_invitation(
    invitation_entity_urn: str,
    invitation_shared_secret: str,
    action: Literal["accept", "reject"] = "accept"
) -> str:
    """Reply to a connection invitation"""
    result = linkedin_client.reply_invitation(
        invitation_entity_urn=invitation_entity_urn,
        invitation_shared_secret=invitation_shared_secret,
        action=action
    )
    return json.dumps({"success": result})

@tool(
    description="Get network information for a LinkedIn profile, including number of connections, followers, and network distance.",
    public_profile_id="The public identifier of the LinkedIn profile",
    safe=True
)
def get_profile_network_info(
    public_profile_id: str
) -> str:
    """Get network information for a profile"""
    network_info = linkedin_client.get_profile_network_info(public_profile_id)
    return json.dumps(network_info)

@tool(
    description="Get privacy settings for a LinkedIn profile.",
    public_profile_id="The public identifier of the LinkedIn profile",
    safe=True
)
def get_profile_privacy_settings(
    public_profile_id: str
) -> str:
    """Get privacy settings for a profile"""
    privacy_settings = linkedin_client.get_profile_privacy_settings(public_profile_id)
    return json.dumps(privacy_settings)

@tool(
    description="Get member badges for a LinkedIn profile.",
    public_profile_id="The public identifier of the LinkedIn profile",
    safe=True
)
def get_profile_member_badges(
    public_profile_id: str
) -> str:
    """Get member badges for a profile"""
    badges = linkedin_client.get_profile_member_badges(public_profile_id)
    return json.dumps(badges)

@tool(
    description="Get detailed work experience information for a LinkedIn profile.",
    urn_id="The URN identifier of the LinkedIn profile",
    safe=True
)
def get_profile_experiences(
    urn_id: str
) -> str:
    """Get work experiences for a profile"""
    experiences = linkedin_client.get_profile_experiences(urn_id)
    return json.dumps(experiences)

@tool(
    description="Get information about a LinkedIn school.",
    public_id="The public identifier of the school",
    safe=True
)
def get_school(
    public_id: str
) -> str:
    """Get information about a school"""
    school = linkedin_client.get_school(public_id)
    return json.dumps(school)

@tool(
    description="Get company updates (news/activity) for a LinkedIn company. You must provide either public_id or urn_id.",
    public_id="The public identifier of the company",
    urn_id="The URN identifier of the company",
    max_results="Maximum number of updates to fetch",
    safe=True
)
def get_company_updates(
    public_id: str = None,
    urn_id: str = None,
    max_results: int = None
) -> str:
    """Get company updates"""
    updates = linkedin_client.get_company_updates(
        public_id=public_id,
        urn_id=urn_id,
        max_results=max_results
    )
    return json.dumps(updates)

@tool(
    description="Follow or unfollow a company on LinkedIn.",
    following_state_urn="The URN state identifier for following the company",
    following="Whether to follow (True) or unfollow (False) the company",
    safe=False
)
def follow_company(
    following_state_urn: str,
    following: bool = True
) -> str:
    """Follow or unfollow a company"""
    result = linkedin_client.follow_company(
        following_state_urn=following_state_urn,
        following=following
    )
    return json.dumps({"success": not result})

@tool(
    description="Get profile view statistics for the current user, including chart data.",
    safe=True
)
def get_current_profile_views() -> str:
    """Get profile view statistics"""
    views = linkedin_client.get_current_profile_views()
    return json.dumps(views)

@tool(
    description="Get posts from the user's LinkedIn feed.",
    limit="Maximum number of posts to fetch (-1 for no limit)",
    offset="Number of posts to skip",
    exclude_promoted_posts="Whether to exclude promoted/sponsored posts",
    safe=True
)
def get_feed_posts(
    limit: int = -1,
    offset: int = 0,
    exclude_promoted_posts: bool = True
) -> str:
    """Get posts from LinkedIn feed"""
    posts = linkedin_client.get_feed_posts(
        limit=limit,
        offset=offset,
        exclude_promoted_posts=exclude_promoted_posts
    )
    return json.dumps(posts)

@tool(
    description="Get required skills for a specific job posting.",
    job_id="The LinkedIn job ID",
    safe=True
)
def get_job_skills(
    job_id: str
) -> str:
    """Get required skills for a job"""
    skills = linkedin_client.get_job_skills(job_id)
    return json.dumps(skills)

@tool(
    description="Unfollow any LinkedIn entity (person, company, etc.).",
    urn_id="The URN identifier of the entity to unfollow",
    safe=False
)
def unfollow_entity(
    urn_id: str
) -> str:
    """Unfollow a LinkedIn entity"""
    result = linkedin_client.unfollow_entity(urn_id)
    return json.dumps({"success": not result})

@tool(
    description="Get the connections for a LinkedIn profile by URN.",
    urn_id="The URN identifier of the LinkedIn profile (e.g., 'urn:li:fs_miniProfile:AbC123')",
    safe=True
)
def get_profile_connections(urn_id: str) -> str:
    """Get the connections for a LinkedIn profile using only the URN ID."""
    results = linkedin_client.get_profile_connections(urn_id=urn_id)
    return json.dumps(results)

# Export the tools
TOOLS = [
    search_people,
    get_profile,
    get_profile_contact_info,
    get_profile_connections,
    # add_connection,
    # remove_connection,
    # search_jobs,
    # get_job,
    send_message,
    get_conversations,
    get_conversation,
    search_companies,
    get_company,
    get_profile_skills,
    get_profile_posts,
    get_post_comments,
    # get_post_reactions,
    # react_to_post,
    # get_invitations,
    # reply_invitation,
    get_profile_network_info,
    # get_profile_privacy_settings,
    # get_profile_member_badges,
    get_profile_experiences,
    get_school,
    # get_company_updates,
    # follow_company,
    # get_current_profile_views,
    get_feed_posts,
    # get_job_skills,
    # unfollow_entity
] 
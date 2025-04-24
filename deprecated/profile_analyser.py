from googlesearch import search
from linkedin_api import Linkedin
import yaml
from ai_core import AI
from config import secrets

ai = AI("gpt4o")

PROMPT = """
I have the following LinkedIn profile data for a person. Please analyze this data and provide an assessment of how powerful and well-connected she is likely to be. Consider factors such as her job titles, companies she has worked for, her educational background, and her roles in various organizations. Provide your output in XML format, with one tag containing the detailed explanation and another tag containing the power and connection factor as a single number between 0 and 10.

LinkedIn Profile Data:

{profile_data}

Output Format:

```xml
<assessment>
    <explanation>Your detailed explanation here.</explanation>
    <powerConnectionFactor>Number between 0 and 10</powerConnectionFactor>
</assessment>
```
"""

api = Linkedin('explainairisk@gmail.com', secrets.LINKEDIN_PASSWORD)

def search_linkedin_profiles(names):
    results = {}
    for name in names:
        query = f"{name} site:linkedin.com"
        search_results = search(query, num_results=10)
        linkedin_urls = [url for url in search_results if "linkedin.com/in/" in url]
        results[name] = linkedin_urls
    return results


def format_linkedin_profile(profile):
    def format_experience(experience):
        exp_str = f"{experience['title']} at {experience['companyName']}\n"
        exp_str += f"Location: {experience.get('locationName', 'N/A')}\n"
        start_date = experience['timePeriod'].get('startDate')
        end_date = experience['timePeriod'].get('endDate', 'Present')
        if start_date:
            start_str = f"{start_date.get('month', 'N/A')}/{start_date.get('year', 'N/A')}"
        else:
            start_str = "N/A"
        if end_date != 'Present':
            end_str = f"{end_date.get('month', 'N/A')}/{end_date.get('year', 'N/A')}"
        else:
            end_str = 'Present'
        exp_str += f"Duration: {start_str} - {end_str}\n"
        exp_str += f"Description: {experience.get('description', 'N/A')}\n"
        exp_str += f"Company Size: {experience['company'].get('employeeCountRange', {}).get('start', 'N/A')}-{experience['company'].get('employeeCountRange', {}).get('end', 'N/A')}\n"
        exp_str += f"Industry: {', '.join(experience['company'].get('industries', []))}\n"
        return exp_str

    def format_education(education):
        edu_str = f"{education['degreeName']} in {education.get('fieldOfStudy', 'N/A')} from {education['schoolName']}\n"
        start_date = education['timePeriod'].get('startDate', {}).get('year', 'N/A')
        end_date = education['timePeriod'].get('endDate', {}).get('year', 'N/A')
        edu_str += f"Duration: {start_date} - {end_date}\n"
        edu_str += f"Description: {education.get('description', 'N/A')}\n"
        return edu_str

    text_profile = f"Name: {profile['firstName']} {profile['lastName']}\n"
    text_profile += f"Headline: {profile.get('headline', 'N/A')}\n"
    text_profile += f"Location: {profile.get('locationName', 'N/A')}, {profile.get('geoCountryName', 'N/A')}\n"
    text_profile += f"Industry: {profile.get('industryName', 'N/A')}\n\n"

    text_profile += "Experience:\n"
    for experience in profile.get('experience', []):
        text_profile += format_experience(experience) + "\n"

    text_profile += "Education:\n"
    for education in profile.get('education', []):
        text_profile += format_education(education) + "\n"

    text_profile += "Certifications:\n"
    for cert in profile.get('certifications', []):
        text_profile += f"{cert['name']} from {cert['authority']}\n"
        text_profile += f"Link: {cert.get('url', 'N/A')}\n\n"

    text_profile += "Volunteer Experience:\n"
    for volunteer in profile.get('volunteer', []):
        text_profile += f"{volunteer['role']} at {volunteer['companyName']}\n"
        text_profile += f"Description: {volunteer.get('description', 'N/A')}\n\n"

    return text_profile


def extract_profiles(names):
    linkedin_profiles = search_linkedin_profiles(names)
    results = []
    for name, profiles in linkedin_profiles.items():
        results.append(profiles)
    return results

name = "Angelina Gentaz"
if __name__ == "__main__":
    linkedin_profiles = extract_profiles([name])
    for profiles in linkedin_profiles:
        for url in profiles:
            linkedin_name = url.rsplit("/", 1)[-1]
            profile = api.get_profile(linkedin_name)
            profile_txt = format_linkedin_profile(profile)
            response = ai.message(PROMPT.format(profile_data=profile_txt))
            print(response)


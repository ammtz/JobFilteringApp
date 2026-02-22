"""
Service for parsing job descriptions into structured requirements
"""
import json
from typing import Dict, Any, Optional
from app.services.llm import openai_chat_json, LLMError


def parse_job_description(raw_text: str, title: Optional[str] = None, company: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse a job description into structured requirements sections.
    
    Returns a dictionary with categorized requirements:
    - about_summary: Brief summary of the role
    - experience_requirements: Years of experience, level, etc.
    - expertise_requirements: Technical skills, tools, technologies
    - business_cultural_requirements: Company values, culture fit, soft skills
    - sponsorship_requirements: Visa sponsorship, international requirements
    - work_location_requirements: Remote, hybrid, in-person requirements
    - education_requirements: Degree, certifications, education level
    """
    
    system_prompt = """You are a job description parser. Extract structured information from job postings.
    
Extract the following categories:
1. about_summary: A 2-3 sentence summary of what the role is about
2. experience_requirements: Years of experience, seniority level, specific experience needed
3. expertise_requirements: Technical skills, programming languages, tools, frameworks, technologies
4. business_cultural_requirements: Company values, culture fit, soft skills, personality traits
5. sponsorship_requirements: Visa sponsorship mentioned, international work authorization, relocation
6. work_location_requirements: Remote, hybrid, in-person, travel requirements, location preferences
7. education_requirements: Degree requirements, certifications, education level, field of study

Return ONLY valid JSON with this exact structure:
{
  "about_summary": "string or null",
  "experience_requirements": "string or null",
  "expertise_requirements": "string or null",
  "business_cultural_requirements": "string or null",
  "sponsorship_requirements": "string or null",
  "work_location_requirements": "string or null",
  "education_requirements": "string or null"
}

If a category is not mentioned in the job description, set it to null. Be concise but comprehensive."""

    user_prompt = f"""Parse this job description:

Title: {title or 'Not specified'}
Company: {company or 'Not specified'}

Description:
{raw_text[:8000]}"""

    try:
        result = openai_chat_json([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        
        # Validate structure
        required_fields = [
            "about_summary",
            "experience_requirements",
            "expertise_requirements",
            "business_cultural_requirements",
            "sponsorship_requirements",
            "work_location_requirements",
            "education_requirements",
        ]
        
        parsed_data = {}
        for field in required_fields:
            value = result.get(field)
            # Convert empty strings to None
            parsed_data[field] = value if value and str(value).strip() else None
        
        return parsed_data
        
    except LLMError as e:
        # Return empty structure on error
        return {
            "about_summary": None,
            "experience_requirements": None,
            "expertise_requirements": None,
            "business_cultural_requirements": None,
            "sponsorship_requirements": None,
            "work_location_requirements": None,
            "education_requirements": None,
            "_error": str(e),
        }
    except Exception as e:
        return {
            "about_summary": None,
            "experience_requirements": None,
            "expertise_requirements": None,
            "business_cultural_requirements": None,
            "sponsorship_requirements": None,
            "work_location_requirements": None,
            "education_requirements": None,
            "_error": f"Unexpected error: {str(e)}",
        }

import json
import os
import re
import time

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


class AIAgent:
    def __init__(self, provider="gemini", api_key=None):
        self.provider = provider
        self.api_keys = [api_key] if api_key else [
            os.getenv("AI_API_KEY"),
            os.getenv("AI_API_KEY_2"),
        ]
        self.api_keys = [key for key in self.api_keys if key]
        self.current_key_index = 0
        self.client = None
        self.model = None
        self.overrides = {
            "name": os.getenv("USER_NAME"),
            "email": os.getenv("USER_EMAIL"),
            "phone": os.getenv("USER_PHONE"),
            "location": os.getenv("USER_LOCATION"),
            "linkedin": os.getenv("USER_LINKEDIN"),
            "portfolio": os.getenv("USER_PORTFOLIO"),
            "website": os.getenv("USER_WEBSITE"),
            "github": os.getenv("USER_GITHUB"),
            "years_experience": os.getenv("USER_YEARS_EXPERIENCE"),
        }
        self._initialize_client()

    def _initialize_client(self):
        self.client = None
        self.model = None
        if not self.api_keys:
            print("No AI API key detected. Using deterministic fallback mode.")
            return

        key = self.api_keys[self.current_key_index]
        print(f"Initializing AI Client with key index {self.current_key_index}...")

        if self.provider == "gemini":
            import google.generativeai as genai

            genai.configure(api_key=key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        elif self.provider == "groq":
            self.client = Groq(api_key=key)
            self.model = "llama-3.1-8b-instant"

    def _query_ai(self, prompt, retry_count=0):
        if not self.model:
            return None

        try:
            print(f"AI Querying {self.provider}...")
            if self.provider == "gemini":
                response = self.model.generate_content(prompt)
                print("AI Response Received.")
                return response.text

            if self.provider == "groq":
                chat_completion = self.client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model,
                )
                print("AI Response Received.")
                return chat_completion.choices[0].message.content
        except Exception as exc:
            message = str(exc).lower()
            if "rate_limit" in message or "limit reached" in message or "429" in message:
                if retry_count < len(self.api_keys) * 2: # Try rotating and then waiting
                    print(f"Rate limit reached on key index {self.current_key_index}. Rotating...")
                    self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                    self._initialize_client()
                    
                    # If we've tried all keys, wait a bit before the next retry
                    if self.current_key_index == 0:
                        wait_time = 30 + (retry_count * 10)
                        print(f"All keys reached limits. Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        
                    return self._query_ai(prompt, retry_count + 1)
                print("Rate limit reached on all keys after multiple retries. Falling back to deterministic mode.")
                return None
            print(f"AI query failed. Falling back to deterministic mode: {exc}")
            return None

        return None

    def _extract_json(self, payload):
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list):
            return {"items": payload}
        if not payload:
            return {}

        try:
            start = payload.find("{")
            end = payload.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(payload[start:end])
            return json.loads(payload)
        except Exception as exc:
            print(f"Error parsing JSON: {exc}")
            return {}

    def _merge_overrides(self, profile):
        merged = dict(profile)
        links = dict(merged.get("Links", {}))

        if self.overrides.get("name"):
            merged["Name"] = self.overrides["name"]
        if self.overrides.get("email"):
            merged["Email"] = self.overrides["email"]
        if self.overrides.get("phone"):
            merged["Phone"] = self.overrides["phone"]
        if self.overrides.get("location"):
            merged["Location"] = self.overrides["location"]

        for label, key in [
            ("LinkedIn", "linkedin"),
            ("GitHub", "github"),
            ("Portfolio", "portfolio"),
            ("Website", "website"),
        ]:
            if self.overrides.get(key):
                links[label] = self.overrides[key]

        if links:
            merged["Links"] = links

        if self.overrides.get("years_experience"):
            merged["YearsExperience"] = self.overrides["years_experience"]

        return merged

    def _regex_extract(self, pattern, text):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _fallback_resume_profile(self, text):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        name = self.overrides.get("name") or (lines[0].title() if lines else "")
        email = self.overrides.get("email") or self._regex_extract(
            r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", text
        )
        phone = self.overrides.get("phone") or self._regex_extract(
            r"(\+?\d[\d\s\-()]{8,}\d)", text
        )
        linkedin = self.overrides.get("linkedin") or self._regex_extract(
            r"(linkedin\.com/in/[^\s|]+)", text
        )
        github = self.overrides.get("github") or self._regex_extract(
            r"(github\.com/[^\s|]+)", text
        )

        skills_section = self._regex_extract(
            r"BLOCKCHAIN\s*&?\s*TECHNICAL\s*SKILLS(.*?)(?:EDUCATION|$)",
            text,
        )
        skills = []
        if skills_section:
            for raw_skill in re.split(r"[,|]\s*|\n", skills_section):
                clean_skill = re.sub(r"^[A-Za-z /&]+:\s*", "", raw_skill).strip(" -")
                if clean_skill and len(clean_skill) > 1:
                    skills.append(clean_skill)

        profile = {
            "Name": name,
            "Email": email,
            "Phone": phone,
            "Location": self.overrides.get("location") or "",
            "Links": {
                "LinkedIn": linkedin,
                "GitHub": github,
                "Portfolio": self.overrides.get("portfolio") or self.overrides.get("website") or "",
            },
            "Skills": list(dict.fromkeys(skills)),
            "Experience": [],
            "Education": [],
            "Projects": [],
            "Summary": lines[1] if len(lines) > 1 else "",
            "raw_text": text,
        }
        return self._merge_overrides(profile)

    def structure_resume(self, text):
        prompt = f"""
        Extract the following information from the resume text into a clean JSON format:
        - Name
        - Email
        - Phone
        - Location
        - Links (LinkedIn, GitHub, Portfolio, Website)
        - Skills (List)
        - Experience (List of objects with Title, Company, Date, Description)
        - Education (List)
        - Projects (List of objects with Name, Description, Link)

        Resume Text:
        {text}

        User Overrides (Use these if they differ from the resume):
        {json.dumps(self.overrides)}

        Return ONLY valid JSON.
        """
        response = self._query_ai(prompt)
        parsed = self._extract_json(response)
        if parsed:
            parsed["raw_text"] = text
            return self._merge_overrides(parsed)
        return self._fallback_resume_profile(text)

    def _tokenize(self, text):
        return {
            token
            for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.\-]{1,}", (text or "").lower())
            if token not in {"with", "from", "that", "this", "have", "will", "your", "their"}
        }

    def _heuristic_match(self, resume_json, job_description):
        resume_blob = " ".join(
            [
                resume_json.get("raw_text", ""),
                " ".join(resume_json.get("Skills", [])),
                json.dumps(resume_json.get("Projects", [])),
                json.dumps(resume_json.get("Experience", [])),
            ]
        )
        resume_tokens = self._tokenize(resume_blob)
        job_tokens = self._tokenize(job_description)

        overlap = sorted(job_tokens & resume_tokens)
        overlap_count = len(overlap)
        score = min(95, 25 + overlap_count * 4)

        blockers = []
        for keyword in ["java", "dotnet", ".net", "salesforce", "swift", "golang"]:
            if keyword in job_tokens and keyword not in resume_tokens:
                blockers.append(keyword)
                score -= 8

        for preferred in ["blockchain", "web3", "solidity", "smart", "contract", "defi", "protocol"]:
            if preferred in job_tokens and preferred in resume_tokens:
                score += 4

        score = max(0, min(100, score))
        overlap_preview = ", ".join(overlap[:8]) if overlap else "limited overlap"
        if blockers:
            reason = f"Matched on {overlap_preview}, but missing {', '.join(blockers[:3])}."
        else:
            reason = f"Matched on {overlap_preview}."
        return {"match_score": score, "reason": reason}

    def match_job(self, resume_json, job_description):
        prompt = f"""
        Compare the following resume data with the job description.
        Resume: {json.dumps(resume_json)}
        Job Description: {job_description[:7000]}

        Return a JSON object with:
        - match_score (0-100)
        - reason (brief explanation)
        """
        response = self._query_ai(prompt)
        parsed = self._extract_json(response)
        if isinstance(parsed.get("match_score"), (int, float)):
            parsed["match_score"] = max(0, min(100, int(parsed["match_score"])))
            return parsed
        return self._heuristic_match(resume_json, job_description)

    def _flatten_profile(self, resume_json):
        links = resume_json.get("Links", {})
        name = (resume_json.get("Name") or "").strip()
        parts = [part for part in name.split() if part]
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
        return {
            "full_name": name,
            "first_name": first_name,
            "last_name": last_name,
            "email": resume_json.get("Email") or "",
            "phone": resume_json.get("Phone") or "",
            "location": resume_json.get("Location") or "",
            "linkedin": links.get("LinkedIn") or "",
            "github": links.get("GitHub") or "",
            "portfolio": links.get("Portfolio") or links.get("Website") or "",
            "website": links.get("Website") or links.get("Portfolio") or "",
            "years_experience": str(resume_json.get("YearsExperience") or self.overrides.get("years_experience") or "1"),
            "summary": resume_json.get("Summary") or "",
        }

    def _default_answer_for_field(self, profile, field):
        label = (field.get("label") or field.get("name") or "").lower()
        field_type = (field.get("type") or "text").lower()

        alias_map = [
            (["first name", "firstname", "given name"], profile["first_name"]),
            (["last name", "lastname", "surname", "family name"], profile["last_name"]),
            (["full name", "your name", "name"], profile["full_name"]),
            (["email", "e-mail"], profile["email"]),
            (["phone", "mobile", "contact number"], profile["phone"]),
            (["linkedin"], profile["linkedin"]),
            (["github"], profile["github"]),
            (["portfolio"], profile["portfolio"]),
            (["website", "personal site"], profile["website"]),
            (["location", "city", "current city", "address"], profile["location"]),
            (["experience", "years of experience"], profile["years_experience"]),
        ]
        for aliases, value in alias_map:
            if any(alias in label for alias in aliases) and value:
                return value

        if field_type == "checkbox":
            if "terms" in label or "privacy" in label or "policy" in label:
                return True
            return None

        if field_type in {"radio", "select-one"}:
            if "authorized" in label:
                return "Yes"
            if "sponsorship" in label or "visa" in label:
                return "No"

        if any(token in label for token in ["why", "cover letter", "summary", "about yourself", "motivation"]):
            summary = profile["summary"] or (
                "I bring hands-on blockchain, AI, and developer community experience and enjoy shipping practical products."
            )
            return summary[:300]

        return None

    def generate_form_answers(self, resume_json, fields):
        profile = self._flatten_profile(resume_json)
        answers = {}
        for field in fields:
            key = field.get("key") or field.get("name") or field.get("label") or "unknown"
            value = self._default_answer_for_field(profile, field)
            if value not in [None, ""]:
                answers[key] = value

        prompt = f"""
        I am applying for a job. Here is my resume: {json.dumps(resume_json)}
        Here are the fields detected on the application page: {json.dumps(fields)}
        Existing deterministic answers: {json.dumps(answers)}

        Only add missing answers for open-ended questions. Keep them concise, professional, and truthful.
        Return ONLY valid JSON.
        """
        response = self._query_ai(prompt)
        ai_answers = self._extract_json(response)
        if isinstance(ai_answers, dict):
            for key, value in ai_answers.items():
                if value not in [None, ""] and key not in answers:
                    answers[key] = value
        return answers

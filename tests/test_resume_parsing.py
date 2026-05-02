import json
import unittest
from pathlib import Path
from unittest.mock import patch

from run_resume_parse import extract_resume_text
from resume_parser import _validate_schema, clean_resume_text, parse_resume, split_sections


def sample_contract_output() -> dict:
    return {
        "candidate_name": "Jordan Chen",
        "skills": [{"name": "Python", "category": "technical"}],
        "education": [
            {
                "degree": "Bachelor of Science in Computer Science",
                "institution": "University of Washington",
                "graduation_year": 2025,
                "gpa": 3.6,
                "relevant_coursework": ["Machine Learning"],
            }
        ],
        "work_experience": [
            {
                "company": "Example Corp",
                "title": "Software Engineering Intern",
                "start_date": "Jun 2024",
                "end_date": "Sep 2024",
                "bullets": [
                    {
                        "text": "Built a serverless pipeline using AWS Lambda.",
                        "skills_mentioned": ["AWS", "Lambda"],
                    }
                ],
            }
        ],
        "projects": [
            {
                "name": "CampusEats",
                "technologies": ["React", "FastAPI"],
                "bullets": [
                    {
                        "text": "Built a web app for campus dining.",
                        "skills_mentioned": ["React", "FastAPI"],
                    }
                ],
            }
        ],
    }


class ResumeParsingTests(unittest.TestCase):
    def test_clean_resume_text_normalizes_bullets_and_page_noise(self) -> None:
        raw = "SKILLS\r\n• Python\r\n-- 1 of 2 --\r\nMachine\nLearning"
        cleaned = clean_resume_text(raw)
        self.assertIn("SKILLS", cleaned)
        self.assertIn("- Python", cleaned)
        self.assertIn("Machine Learning", cleaned)
        self.assertNotIn("-- 1 of 2 --", cleaned)

    def test_split_sections_marks_known_sections(self) -> None:
        text = "Skills\nPython\n\nEducation\nUTS\n\nProjects\nResume Parser"
        sectioned = split_sections(text)
        self.assertIn("[SECTION:skills]", sectioned)
        self.assertIn("[SECTION:education]", sectioned)
        self.assertIn("[SECTION:projects]", sectioned)

    def test_validate_schema_accepts_contract_shape(self) -> None:
        self.assertTrue(_validate_schema(sample_contract_output()))

    def test_validate_schema_rejects_missing_nested_fields(self) -> None:
        broken = sample_contract_output()
        broken["work_experience"][0]["bullets"][0].pop("skills_mentioned")
        self.assertFalse(_validate_schema(broken))

    @patch("resume_parser.call_llm")
    def test_parse_resume_retries_after_invalid_json(self, mock_call_llm) -> None:
        expected = sample_contract_output()
        mock_call_llm.side_effect = ["not-json", json.dumps(expected)]

        parsed = json.loads(parse_resume("Skills\nPython"))

        self.assertEqual(parsed["candidate_name"], "Jordan Chen")
        self.assertEqual(mock_call_llm.call_count, 2)

    @patch("resume_parser.call_llm")
    def test_parse_resume_falls_back_to_empty_contract(self, mock_call_llm) -> None:
        mock_call_llm.side_effect = ["{}", "still-not-json"]

        parsed = json.loads(parse_resume("Skills\nPython"))

        self.assertEqual(
            parsed,
            {
                "candidate_name": None,
                "skills": [],
                "education": [],
                "work_experience": [],
                "projects": [],
            },
        )

    def test_extract_resume_text_rejects_unsupported_extension(self) -> None:
        with self.assertRaises(ValueError):
            extract_resume_text(Path("resume.txt"))


if __name__ == "__main__":
    unittest.main()

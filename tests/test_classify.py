import unittest
from profession_monitor.classify import classify_job, extract_skills

class ClassifyTests(unittest.TestCase):
    def test_classifies_role_families_and_rejects_data_entry(self):
        self.assertEqual(classify_job("Senior Data Scientist", "").family, "data-science-ml")
        self.assertEqual(classify_job("BI Data Analyst", "").family, "analyst-bi")
        self.assertEqual(classify_job("Analytics Engineer", "").family, "data-engineering")
        self.assertEqual(classify_job("Quantitative Risk Analyst", "").family, "quant-risk")
        self.assertFalse(classify_job("Data Entry Administrator", "").relevant)

    def test_extracts_normalized_skills(self):
        skills = extract_skills("Python, SQL, Power BI, AWS and machine learning with Docker")
        self.assertEqual(skills, ["AWS", "Docker", "Machine learning", "Power BI", "Python", "SQL"])

if __name__ == "__main__": unittest.main()

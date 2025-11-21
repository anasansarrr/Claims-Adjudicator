from google import genai

client = genai.Client(api_key="AIzaSyAOZV2Yg2A05HKtD24zXnkoYZeZH9G-ZbQ")

prompt = "State your exact model identifier only."

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt
)

print(response.text)

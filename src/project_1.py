import boto3
import botocore.config
import json
from datetime import datetime

# Map language names (lowercase) to (extension, MIME content-type)
LANGUAGE_META = {
    "python":       ("py",     "text/x-python"),
    "javascript":   ("js",     "text/javascript"),
    "typescript":   ("ts",     "text/typescript"),
    "java":         ("java",   "text/x-java-source"),
    "go":           ("go",     "text/x-go"),
    "golang":       ("go",     "text/x-go"),
    "rust":         ("rs",     "text/x-rust"),
    "c":            ("c",      "text/x-c"),
    "c++":          ("cpp",    "text/x-c++"),
    "cpp":          ("cpp",    "text/x-c++"),
    "c#":           ("cs",     "text/x-csharp"),
    "csharp":       ("cs",     "text/x-csharp"),
    "ruby":         ("rb",     "text/x-ruby"),
    "php":          ("php",    "text/x-php"),
    "swift":        ("swift",  "text/x-swift"),
    "kotlin":       ("kt",     "text/x-kotlin"),
    "shell":        ("sh",     "text/x-shellscript"),
    "bash":         ("sh",     "text/x-shellscript"),
    "sql":          ("sql",    "text/x-sql"),
    "html":         ("html",   "text/html"),
    "css":          ("css",    "text/css"),
    "yaml":         ("yaml",   "text/yaml"),
    "json":         ("json",   "application/json"),
    "terraform":    ("tf",     "text/x-hcl"),
    "hcl":          ("tf",     "text/x-hcl"),
}


def language_meta(language: str):
    """Return (extension, content_type) for a language, defaulting to ('txt', 'text/plain')."""
    return LANGUAGE_META.get(language.strip().lower(), ("txt", "text/plain"))


def generate_code_using_bedrock(message: str, language: str) -> str:
    system_prompt = f"""You are a helpful coding assistant. Always respond with only the requested code, without explanations or markdown formatting. 
    Make sure you write in the format of that language, instead of markdown file.
    """
    user_prompt = f"Write {language} code for the following instruction: {message}"

    body = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 2048,
        "temperature": 0.1,
        "top_p": 0.2,
    }

    try:
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1",
                               config=botocore.config.Config(read_timeout=300, retries={"max_attempts": 3}))
        response = bedrock.invoke_model(body=json.dumps(body),
                                        modelId="deepseek.v3.2")
        response_content = response.get("body").read().decode("utf-8")
        response_data = json.loads(response_content)
        code = response_data["choices"][0]["message"]["content"].strip()
        return code
    except Exception as e:
        print(f"Error generating code: {str(e)}")
        raise e


def save_code_to_s3_bucket(code, s3bucket, s3_key, content_type):
    s3 = boto3.client('s3')
    try:
        s3.put_object(Bucket=s3bucket, Key=s3_key,
                      Body=code, ContentType=content_type)
        print("code saved to s3")
    except Exception as e:
        print(f"Error saving code to S3: {str(e)}")
        raise e

# SafeLine HACCP Audit Assistant - Run Guide

This guide shows how to run the HACCP RAG project on Windows using PowerShell.

## 1. Open the project folder

Open PowerShell, then run:

```powershell
cd C:\Users\HP\Desktop\YUVA
```

## 2. Activate the virtual environment

The project uses a local Python environment called `.venv`.

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script, run this command once in the same window and try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 3. Install the required packages

With the environment activated, install all project dependencies:

```powershell
python -m pip install -r requirements.txt
```

The first installation can take a few minutes because LangChain and the local embedding model dependencies are downloaded.

### Fix for the `torchvision` error

If you see this error:

```text
ModuleNotFoundError: No module named 'torchvision'
```

install the missing package and restart the app:

```powershell
python -m pip install torchvision==0.14.0
```

This message is produced by Streamlit inspecting optional image modules in `transformers`; it is unrelated to your uploaded HACCP documents.

## 4. Add your Groq API key

1. Get an API key from [Groq Console](https://console.groq.com/keys).
2. Create a local environment file if it does not already exist:

   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```

3. Open `.env` in Notepad:

   ```powershell
   notepad .env
   ```

4. Replace the placeholder value with your key:

   ```text
   GROQ_API_KEY=gsk_your_real_key_here
   ```

5. Save and close Notepad.

Never share your `.env` file or Groq API key. The project’s `.gitignore` prevents it from being committed to Git.

## 5. Start the application

Run:

```powershell
streamlit run app.py
```

PowerShell will show a local URL, normally:

```text
http://localhost:8501
```

Open that address in your browser if it does not open automatically. Keep the PowerShell window running while you use the app. Stop the app with `Ctrl + C`.

## 6. Run your first HACCP audit

1. In **Governing rules**, upload the HACCP rules or standard. Use the supplied USDA HACCP PDF here.
2. In **Document to assess**, upload the HACCP plan, SOP, inspection report, or process document to review.
3. Select the relevant **Focus areas** in the audit controls.
4. Enter an audit brief. Example:

   ```text
   Analyze this HACCP plan against the uploaded rules. Identify food-safety gaps,
   prioritise risk, and state what must be corrected before approval.
   ```

5. Select **Run audit**.
6. Review the findings in **Audit report** and inspect the cited excerpts in **Source evidence**.
7. Use **Download audit report** to save the Markdown audit record.

## Supported files

| Use | Supported formats |
| --- | --- |
| Rules / standards | PDF, DOCX, TXT, Markdown |
| Documents to assess | PDF, DOCX, TXT, Markdown |

For a scanned PDF, the file must contain selectable/OCR text. A photo-only scan cannot be reliably retrieved until it has been OCR processed.

## Troubleshooting

### `GROQ_API_KEY is missing`

Check that the file is named exactly `.env`, is in `C:\Users\HP\Desktop\YUVA`, and contains a non-placeholder Groq key. Restart Streamlit after changing it.

### `Could not read` or `No readable text was found`

The file may be encrypted, corrupted, or a scanned image PDF. Export it as a searchable PDF or DOCX, then upload it again.

### The first audit is slow

This is normal. The local HuggingFace embedding model is downloaded on its first use. Future audits are usually faster.

### Port 8501 is already in use

Start Streamlit on another port:

```powershell
streamlit run app.py --server.port 8502
```

## Important note

SafeLine is designed to support HACCP review, not replace a qualified food-safety professional or a regulatory authority. Validate all findings before making operational or compliance decisions.

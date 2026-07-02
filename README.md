# Product Sourcing Intelligence Agent

This project implements a "Product Sourcing Intelligence Agent" that allows users to upload an image, perform a reverse image search to find similar products online, scrape data from those product listings, and generate a synthesized AI-powered intelligence report.

## Technical Stack

*   **Backend:** Python with FastAPI
*   **Frontend:** React/Next.js

## Features

*   **Image Upload:** Accepts a multipart/form-data image file.
*   **Reverse Image Search (Mocked):** Simulates calling a vision API (Google Vision/Azure Computer Vision) to find matching product URLs.
*   **Parallel Web Scraping (Mocked):** Scrapes the top 5 matching URLs in parallel for product details like images, price, availability, description, reviews, and specifications.
*   **AI-Powered Report Generation (Mocked):** Synthesizes the scraped data into a single, unbiased product intelligence report using an AI model (OpenAI GPT-4/Claude API).
*   **Structured Output:** Returns a JSON object containing the AI report, aggregated images, and PDF/video links.
*   **Error Handling:** Provides a soft error if fewer than 3 product matches are found.

## Project Structure

The project is split into two self-contained apps that communicate over HTTP:

```
backend/    FastAPI service (main.py, requirements.txt)
frontend/   Next.js app (pages/, components/, package.json)
```

## Setup Instructions

### 1. Backend Setup (FastAPI)

1.  **Create and activate a Python virtual environment:**
    ```bash
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    ```
    (You will see a `(venv)` prefix in your terminal, indicating the virtual environment is active.)

2.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *If you encounter an `externally-managed-environment` error, activating the virtual environment as shown above should resolve it.*

3.  **Run the FastAPI server:**
    ```bash
    uvicorn main:app --reload
    ```
    The backend will start on `http://127.0.0.1:8000`. You can access the interactive API documentation (Swagger UI) at `http://127.0.0.1:8000/docs`.

4.  **Deactivate the virtual environment** (when you're done working on the backend):
    ```bash
    deactivate
    ```

### 2. Frontend Setup (React/Next.js)

1.  **Install Node.js dependencies:**
    ```bash
    cd frontend
    npm install
    ```

2.  **Run the Next.js development server:**
    ```bash
    npm run dev
    ```
    The frontend will be accessible at `http://localhost:3000`.

## How to Test the Application

1.  **Ensure both Backend and Frontend are running.**
    *   FastAPI: `http://127.0.0.1:8000`
    *   Next.js: `http://localhost:3000`

2.  **Open your browser** to `http://localhost:3000`. You will see the "Product Sourcing Intelligence Agent" interface.

3.  **Upload an image:**
    *   Click the "Choose File" button and select any image file from your computer.
    *   Click the "Upload & Get Report" button.

4.  **Observe the results:**
    *   The frontend will show a "Processing..." message.
    *   The FastAPI backend (in your terminal where `uvicorn` is running) will print messages indicating the simulation of reverse image search, scraping, and AI report generation.
    *   Once complete, the frontend will display the AI-generated report, aggregated product images, and any found PDF/video links.

### Testing Specific Scenarios

Since external APIs are mocked, you can trigger specific behaviors:

*   **Trigger "Less than 3 matches" error:**
    *   Upload an image file named `blurry_photo.jpg` (or any file with `blurry_photo` in its name, case-insensitive).
    *   The backend's `call_reverse_image_api` placeholder is designed to return fewer than 3 URLs for this specific filename pattern, triggering the `HTTPException` with a `400` status code.
    *   The frontend will display the error message: "Less than 3 product matches found. Please try again with a clearer photo."

*   **Standard Report Generation:**
    *   Upload any other image file (e.g., `product.png`, `item.jpeg`).
    *   The `call_reverse_image_api` will return 5+ dummy URLs, leading to a full report generation.

Remember that all data (URLs, scraped content, AI report text) are currently simulated. For a real-world application, you would replace the placeholder functions in `main.py` with actual API calls to Google Vision/Azure Computer Vision, a web scraping library (e.g., Beautiful Soup, Playwright), and OpenAI/Claude API SDKs.

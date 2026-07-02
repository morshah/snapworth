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

## Setup Instructions

### 1. Backend Setup (FastAPI)

1.  **Navigate to the project root:**
    ```bash
    cd /product-sourcing-agent
    ```
2.  **Install Python dependencies:**
    ```bash
    pip install fastapi uvicorn pydantic python-multipart
    ```
3.  **Run the FastAPI server:**
    ```bash
    uvicorn main:app --reload
    ```
    The backend will start on `http://127.0.0.1:8000`. You can access the interactive API documentation (Swagger UI) at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup (React/Next.js)

1.  **Initialize a Next.js project (if not already done):**
    If your current directory is not already a Next.js project, you'll need to set one up. Run the following command in the project root:
    ```bash
    npx create-next-app . --ts --eslint --use-npm --src-dir # or --use-yarn if you prefer
    ```
    *   When prompted for the project name, enter `.` to create the project in the current directory.
    *   You can typically say `No` to App Router and `Yes` to `src` directory if you prefer that structure.
    *   *If you chose to use a `src` directory*, ensure the `components` and `pages` folders (which I've already created for you) are moved inside the newly created `src` folder.
    *   If you already have a Next.js project set up, ensure the `components` and `pages` folders are in the correct location (e.g., directly in the root or within a `src` directory).

2.  **Install Node.js dependencies:**
    ```bash
    npm install react react-dom next
    ```
    (These are usually installed by `create-next-app`, but run this if you encounter issues.)

3.  **Run the Next.js development server:**
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

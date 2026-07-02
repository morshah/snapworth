import React, { useState } from 'react';

const API_BASE_URL = 'http://127.0.0.1:8000'; // Replace with your backend URL

function ImageUploadForm() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [error, setError] = useState(null);

  const handleFileChange = (event) => {
    setSelectedFile(event.target.files[0]);
    setReportData(null); // Clear previous results
    setError(null);      // Clear previous errors
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError("Please select an image to upload.");
      return;
    }

    setLoading(true);
    setError(null);
    setReportData(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch(`${API_BASE_URL}/upload-image`, {
        method: 'POST',
        body: formData,
        // When using FormData, Content-Type header is usually set automatically
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setReportData(data);
    } catch (err) {
      console.error("Upload failed:", err);
      setError(err.message || "Failed to generate report. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ fontFamily: 'Arial, sans-serif', maxWidth: '800px', margin: '20px auto', padding: '20px', border: '1px solid #ccc', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
      <h1>Product Sourcing Intelligence Agent</h1>

      <div style={{ marginBottom: '20px', padding: '15px', border: '1px solid #eee', borderRadius: '5px', backgroundColor: '#f9f9f9' }}>
        <input type="file" accept="image/*" onChange={handleFileChange} />
        <button
          onClick={handleUpload}
          disabled={loading || !selectedFile}
          style={{ marginLeft: '10px', padding: '8px 15px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer', opacity: loading ? 0.7 : 1 }}
        >
          {loading ? 'Processing...' : 'Upload & Get Report'}
        </button>
        {selectedFile && <p style={{ marginTop: '10px', fontSize: '0.9em', color: '#555' }}>Selected: {selectedFile.name}</p>}
      </div>

      {error && (
        <div style={{ color: '#dc3545', backgroundColor: '#f8d7da', border: '1px solid #f5c6cb', borderRadius: '5px', padding: '10px', marginBottom: '20px' }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {reportData && (
        <div style={{ marginTop: '30px', borderTop: '1px solid #eee', paddingTop: '20px' }}>
          <h2>Product Intelligence Report</h2>
          <h3 style={{ color: '#0056b3' }}>Summary</h3>
          <p>{reportData.report.summary}</p>

          <h3 style={{ color: '#0056b3' }}>Features List</h3>
          <ul style={{ listStyleType: 'disc', marginLeft: '20px' }}>
            {reportData.report.features_list.map((feature, index) => (
              <li key={index}>{feature}</li>
            ))}
          </ul>

          <h3 style={{ color: '#0056b3' }}>Specifications</h3>
          <pre style={{ backgroundColor: '#f0f0f0', padding: '10px', borderRadius: '5px', overflowX: 'auto' }}>
            {JSON.stringify(reportData.report.specs, null, 2)}
          </pre>

          <h3 style={{ color: '#0056b3' }}>Pricing Summary</h3>
          <p>{reportData.report.pricing_summary}</p>

          <h3 style={{ color: '#0056b3' }}>Recommendation Sentiment</h3>
          <p>{reportData.report.recommendation_sentiment}</p>

          <h3 style={{ color: '#28a745' }}>Images ({reportData.images.length})</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: '10px' }}>
            {reportData.images.map((imgUrl, index) => (
              <div key={index} style={{ border: '1px solid #ddd', borderRadius: '4px', overflow: 'hidden' }}>
                <img
                  src={imgUrl}
                  alt={`Product Image ${index + 1}`}
                  style={{ width: '100%', height: 'auto', display: 'block' }}
                  onError={(e) => { e.target.onerror = null; e.target.src="/placeholder-image.png"; e.target.alt="Image failed to load"; }} // Fallback
                />
              </div>
            ))}
          </div>

          {(reportData.pdf_links.length > 0 || reportData.video_links.length > 0) && (
            <>
              <h3 style={{ color: '#0056b3', marginTop: '20px' }}>Additional Resources</h3>
              {reportData.pdf_links.length > 0 && (
                <div>
                  <h4>PDF Links:</h4>
                  <ul style={{ listStyleType: 'none', padding: 0 }}>
                    {reportData.pdf_links.map((link, index) => (
                      <li key={`pdf-${index}`}><a href={link} target="_blank" rel="noopener noreferrer">{link}</a></li>
                    ))}
                  </ul>
                </div>
              )}
              {reportData.video_links.length > 0 && (
                <div>
                  <h4>Video Links:</h4>
                  <ul style={{ listStyleType: 'none', padding: 0 }}>
                    {reportData.video_links.map((link, index) => (
                      <li key={`video-${index}`}><a href={link} target="_blank" rel="noopener noreferrer">{link}</a></li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default ImageUploadForm;
import React, { useState, useEffect, useRef } from 'react';
import { MeiliSearch } from 'meilisearch';

const MEILI_URL = 'http://localhost:7709';
const MEILI_KEY = 'masterKey';
const client = new MeiliSearch({ host: MEILI_URL, apiKey: MEILI_KEY });

const App = () => {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState([]);
    const [feed, setFeed] = useState([]);
    const [isLive, setIsLive] = useState(false);
    const [searching, setSearching] = useState(false);

    useEffect(() => {
        const eventSource = new EventSource('/api/cdc-stream');

        eventSource.onopen = () => {
            setIsLive(true);
        };

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            setFeed((prev) => [data, ...prev].slice(0, 20));
            // Trigger an animation on the indicator
            const indicator = document.querySelector('[data-testid="live-indicator"]');
            if (indicator) {
                indicator.classList.add('pulse');
                setTimeout(() => indicator.classList.remove('pulse'), 500);
            }
            // Refresh search results if relevant
            if (query) {
                searchIndex(query);
            }
        };

        eventSource.onerror = (e) => {
            console.error('SSE Error:', e);
            setIsLive(false);
            // Don't close, let EventSource handle reconnection
        };

        return () => {
            eventSource.close();
        };
    }, [query]);

    const searchIndex = async (q) => {
        setSearching(true);
        try {
            const index = client.index('products');
            const response = await index.search(q, { limit: 10 });
            setResults(response.hits);
        } catch (error) {
            console.error('Search error:', error);
        } finally {
            setSearching(false);
        }
    };

    const handleSearch = (e) => {
        const q = e.target.value;
        setQuery(q);
        if (q.trim()) {
            searchIndex(q);
        } else {
            setResults([]);
        }
    };

    return (
        <div className="app-container">
            <header className="glass">
                <h1>CDC Pipeline Dashboard</h1>
                <div className="status-indicator">
                    <div 
                        data-testid="live-indicator" 
                        className={`indicator ${isLive ? 'online' : 'offline'}`}
                    ></div>
                    <span>{isLive ? 'LIVE' : 'DISCONNECTED'}</span>
                </div>
            </header>

            <main>
                <section className="search-section card">
                    <h2>Search Products</h2>
                    <div className="search-box">
                        <input
                            type="text"
                            data-testid="search-input"
                            placeholder="Type to search products..."
                            value={query}
                            onChange={handleSearch}
                            className="premium-input"
                        />
                        {searching && <div className="loader"></div>}
                    </div>
                    <div data-testid="search-results" className="search-results">
                        {results.length > 0 ? (
                            results.map((hit) => (
                                <div key={hit.id} className="result-item">
                                    <h3>{hit.name}</h3>
                                    <p>{hit.description}</p>
                                    <span className="price">${hit.price}</span>
                                </div>
                            ))
                        ) : query ? (
                            <p className="no-results">No products found for "{query}"</p>
                        ) : (
                            <p className="no-results">Start typing to see results...</p>
                        )}
                    </div>
                </section>

                <section className="feed-section card">
                    <h2>Real-time CDC Feed</h2>
                    <div data-testid="cdc-feed" className="cdc-feed">
                        {feed.length > 0 ? (
                            feed.map((event, idx) => (
                                <div key={idx} className="feed-item">
                                    <span className={`badge ${event.operation.toLowerCase()}`}>
                                        {event.operation}
                                    </span>
                                    <span className="table-name">{event.table}</span>
                                    <span className="timestamp">{new Date(event.timestamp).toLocaleTimeString()}</span>
                                </div>
                            ))
                        ) : (
                            <p className="no-results">Waiting for database events...</p>
                        )}
                    </div>
                </section>
            </main>

            <footer>
            </footer>
        </div>
    );
};

export default App;

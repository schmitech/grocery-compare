// Example React hook for using the API
import { useState } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

export function useGroceryApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Chat with the grocery bot
  const chatWithBot = async (query, aiProvider = 'auto', selectedStores = []) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.post(`${API_URL}/chat`, {
        query,
        ai_provider: aiProvider,
        selected_stores: selectedStores
      });
      
      setLoading(false);
      return response.data;
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred');
      setLoading(false);
      throw err;
    }
  };

  // Compare prices for a specific item
  const compareItems = async (item, aiProvider = 'auto') => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.post(`${API_URL}/compare`, {
        item,
        ai_provider: aiProvider
      });
      
      setLoading(false);
      return response.data;
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred');
      setLoading(false);
      throw err;
    }
  };

  // Get available stores
  const getStores = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.get(`${API_URL}/stores`);
      setLoading(false);
      return response.data.stores;
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred');
      setLoading(false);
      throw err;
    }
  };

  // Search for grocery deals
  const searchDeals = async (query, store = null) => {
    setLoading(true);
    setError(null);
    
    try {
      const params = { query };
      if (store) params.store = store;
      
      const response = await axios.get(`${API_URL}/search`, { params });
      setLoading(false);
      return response.data;
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred');
      setLoading(false);
      throw err;
    }
  };

  return {
    loading,
    error,
    chatWithBot,
    compareItems,
    getStores,
    searchDeals
  };
}
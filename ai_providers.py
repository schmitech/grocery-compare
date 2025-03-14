import os
import warnings
import openai
from dotenv import load_dotenv
import json
from abc import ABC, abstractmethod

# Control debug printing
DEBUG_PRINT = False  # Set to False to reduce output

# Print current working directory to see where we're loading from
if DEBUG_PRINT:
    print(f"Current working directory in ai_providers.py: {os.getcwd()}")

# Load environment variables from .env file with override=True to force reload
dotenv_path = os.path.join(os.getcwd(), ".env")
if os.path.exists(dotenv_path):
    if DEBUG_PRINT:
        print(f"Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path, override=True)
else:
    print(f"Warning: .env file not found at {dotenv_path}")

# Print the loaded environment variables for debugging
if DEBUG_PRINT:
    print(f"ai_providers.py - OPENAI_API_KEY exists: {os.getenv('OPENAI_API_KEY') is not None}")
    if os.getenv('OPENAI_API_KEY'):
        print(f"ai_providers.py - OPENAI_API_KEY last 4 chars: ...{os.getenv('OPENAI_API_KEY')[-4:]}")
    print(f"ai_providers.py - GOOGLE_API_KEY exists: {os.getenv('GOOGLE_API_KEY') is not None}")
    if os.getenv('GOOGLE_API_KEY'):
        print(f"ai_providers.py - GOOGLE_API_KEY last 4 chars: ...{os.getenv('GOOGLE_API_KEY')[-4:]}")

# Check if OpenAI API key is available
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_AVAILABLE = OPENAI_API_KEY is not None and OPENAI_API_KEY != ""
OPENAI_API_NOT_AVAILABLE_MSG = "OpenAI API key not found. Please set the OPENAI_API_KEY environment variable in a .env file."

# Check if Google API key is available
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Initialize Google API if key is available
GOOGLE_AVAILABLE = False
if GOOGLE_API_KEY is not None and GOOGLE_API_KEY != "":
    try:
        import google.generativeai as genai
        GOOGLE_AVAILABLE = True
        
        # Check if GOOGLE_GENAI_MODEL is set, if not, set a default
        GOOGLE_GENAI_MODEL = os.getenv("GOOGLE_GENAI_MODEL")
        if not GOOGLE_GENAI_MODEL:
            print("GOOGLE_GENAI_MODEL not set, using default: gemini-pro")
            os.environ["GOOGLE_GENAI_MODEL"] = "gemini-pro"
    except ImportError:
        warnings.warn("Google Gemini API not available. Install with: pip install google-generativeai")
    except Exception as e:
        warnings.warn(f"Error configuring Google Gemini API: {str(e)}")

GOOGLE_API_NOT_AVAILABLE_MSG = "Google API key not found or Gemini library not installed. Please set the GOOGLE_API_KEY environment variable in a .env file and install google-generativeai."

# Get the default AI provider from environment
DEFAULT_AI_PROVIDER = os.getenv("DEFAULT_AI_PROVIDER", "auto")
print(f"DEFAULT_AI_PROVIDER from .env: {DEFAULT_AI_PROVIDER}")
print(f"OpenAI available: {OPENAI_AVAILABLE}, Google available: {GOOGLE_AVAILABLE}")

# Abstract base class for AI providers
class AIProvider(ABC):
    @abstractmethod
    def get_response(self, prompt, search_results=None):
        """Get a response from the AI provider."""
        pass
    
    @abstractmethod
    def is_available(self):
        """Check if the AI provider is available."""
        pass
    
    @abstractmethod
    def get_unavailable_message(self):
        """Get a message explaining why the AI provider is unavailable."""
        pass

# OpenAI provider
class OpenAIProvider(AIProvider):
    def __init__(self):
        """Initialize the OpenAI provider."""
        if OPENAI_AVAILABLE:
            self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    def is_available(self):
        """Check if OpenAI is available."""
        return OPENAI_AVAILABLE
    
    def get_unavailable_message(self):
        """Get a message explaining why OpenAI is unavailable."""
        return OPENAI_API_NOT_AVAILABLE_MSG
    
    def get_response(self, prompt, search_results=None):
        """
        Get a response from OpenAI's API.
        
        Args:
            prompt: The prompt to send to OpenAI
            search_results: Optional search results to include in the prompt
            
        Returns:
            str: The response from OpenAI, or an error message if the API is not available
        """
        if not self.is_available():
            return self.get_unavailable_message()
        
        # Create a system message that instructs the model how to respond
        system_message = """You are a helpful assistant that provides information about grocery deals across multiple stores.

IMPORTANT GUIDELINES:
1. Focus on directly answering the user's question about grocery deals.
2. When comparing items, use unit prices ($/kg, $/lb) when available for accurate comparisons.
3. Clearly state which store has the better deal and WHY (e.g., "Store A's apples are cheaper at $1.99/lb vs Store B's $2.49/lb").
4. If a product has a unit price in the description (e.g., "$13.21/kg"), use this information in your comparison.
5. Format your response using clean, simple markdown:
   - Use ### for main headings (e.g., "### Best Fruit Deals")
   - Use #### for subheadings (e.g., "#### Farm Boy")
   - Use bullet points (- item) for lists
   - Use **bold** for important information
   - End your response with a "### Best Deal" section that summarizes the best options
6. DO NOT use HTML tags or any complex formatting - stick to basic markdown only.
7. ALWAYS ensure proper spacing between words, numbers, and symbols (e.g., "$0.99 each" NOT "$0.99each").
8. If the user asks about a specific product, focus on that product and similar alternatives.
9. Don't list irrelevant products that don't match what the user is looking for.
10. If no exact matches are found, suggest the closest alternatives.

Your goal is to help users find the best deals and make informed shopping decisions."""
        
        # Create the user message with the prompt
        user_message = prompt
        
        # If search results are provided, include them in the prompt
        if search_results:
            # Format the search results as a string
            from grocery_search import format_results_for_prompt
            results_str = format_results_for_prompt(search_results)
            user_message += f"\n\nHere are the relevant grocery deals I found:\n{results_str}"
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",  # You can change this to a different model if needed
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=800,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error getting response from OpenAI: {str(e)}"

# Google Gemini provider
class GoogleProvider(AIProvider):
    """Provider for Google Gemini API."""
    
    def __init__(self):
        """Initialize the Google Gemini API client."""
        self.client = None
        self.model_name = os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.0-flash")
        print(f"Initializing Google provider with model: {self.model_name}")
    
    def is_available(self):
        """Check if Google Gemini is available."""
        return GOOGLE_AVAILABLE
    
    def get_unavailable_message(self):
        """Get a message explaining why Google Gemini is unavailable."""
        return GOOGLE_API_NOT_AVAILABLE_MSG
    
    def _ensure_client_initialized(self):
        """Ensure the client is initialized."""
        if self.client is None and GOOGLE_AVAILABLE:
            try:
                import google.generativeai as genai
                
                # Get the API key from environment
                api_key = os.getenv("GOOGLE_API_KEY")
                if not api_key:
                    print("GOOGLE_API_KEY not found in environment variables.")
                    return False
                
                # Configure the API
                genai.configure(api_key=api_key)
                
                # Store the client
                self.client = genai
                return True
            except Exception as e:
                print(f"Error initializing Google Gemini API: {e}")
                return False
        return self.client is not None
    
    def get_response(self, prompt, search_results=None):
        """
        Get a response from the Google Gemini API.
        
        Args:
            prompt: The prompt to send to the API
            search_results: Optional search results to include in the prompt
            
        Returns:
            str: The response from the API
        """
        if not self.is_available():
            return self.get_unavailable_message()
        
        if not self._ensure_client_initialized():
            return "Failed to initialize Google Gemini API client."
        
        try:
            print(f"Using Google Gemini API with model: {self.model_name}")
            
            # Create a system message that instructs the model how to respond
            system_message = """You are a helpful assistant that provides information about grocery deals. 
Your goal is to help users find the best deals on groceries.

IMPORTANT GUIDELINES:
1. Focus on directly answering the user's question about grocery deals.
2. When comparing items, use unit prices ($/kg, $/lb) when available for accurate comparisons.
3. Clearly state which store has the better deal and WHY (e.g., "Store A's apples are cheaper at $1.99/lb vs Store B's $2.49/lb").
4. Format your response using clean, simple markdown:
   - Use ### for main headings (e.g., "### Best Fruit Deals")
   - Use #### for subheadings (e.g., "#### Farm Boy")
   - Use bullet points (- item) for lists
   - Use **bold** for important information
   - End your response with a "### Best Deal" section that summarizes the best options
5. DO NOT use HTML tags or any complex formatting - stick to basic markdown only.
6. ALWAYS ensure proper spacing between words, numbers, and symbols (e.g., "$0.99 each" NOT "$0.99each").
7. If the user asks about a specific product, focus on that product and similar alternatives.
8. Don't list irrelevant products that don't match what the user is looking for.
9. If no exact matches are found, suggest the closest alternatives.

Always be honest and accurate in your responses."""
            
            # If search results are provided, include them in the prompt
            user_message = prompt
            if search_results:
                # Format the search results as a string
                from grocery_search import format_results_for_prompt
                results_str = format_results_for_prompt(search_results)
                user_message += f"\n\nHere are the relevant grocery deals I found:\n{results_str}"
                print("Added search results to prompt")
            
            # Check if the prompt contains structured data (JSON)
            contains_structured_data = "```" in user_message and "{" in user_message and "}" in user_message
            
            if contains_structured_data:
                # Add instructions for handling structured data
                system_message += """
                The user has provided structured data in JSON format. Please analyze this data carefully.
                Extract relevant information from the structured data to provide accurate comparisons.
                Focus on price differences, unit prices, and identifying the best deals."""
            
            # Format the prompt for the API call
            formatted_prompt = f"{system_message}\n\n{user_message}"
            
            # Try different API approaches in sequence
            # Approach 1: Try using the GenerativeModel class (newer versions)
            if hasattr(self.client, 'GenerativeModel'):
                try:
                    print("Using GenerativeModel API")
                    model = self.client.GenerativeModel(self.model_name)
                    response = model.generate_content(formatted_prompt)
                    if hasattr(response, 'text'):
                        return response.text
                    else:
                        return str(response)
                except Exception as e:
                    print(f"GenerativeModel approach failed: {e}")
            
            # Approach 2: Try using the generate_text method (older versions)
            if hasattr(self.client, 'generate_text'):
                try:
                    print("Using generate_text API")
                    response = self.client.generate_text(
                        model=self.model_name,
                        prompt=formatted_prompt,
                        temperature=0.2,
                        max_output_tokens=2048,
                    )
                    if hasattr(response, 'text'):
                        return response.text
                    else:
                        return str(response)
                except Exception as e:
                    print(f"generate_text approach failed: {e}")
            
            # Approach 3: Try using the completion method (some versions)
            if hasattr(self.client, 'completion'):
                try:
                    print("Using completion API")
                    response = self.client.completion(
                        model=self.model_name,
                        prompt=formatted_prompt,
                        temperature=0.2,
                        max_output_tokens=2048,
                    )
                    if hasattr(response, 'text'):
                        return response.text
                    else:
                        return str(response)
                except Exception as e:
                    print(f"completion approach failed: {e}")
            
            # If all approaches failed, return an error
            return "Failed to generate response with Google Gemini API. All API approaches failed."
                
        except Exception as e:
            error_message = f"Error getting response from Google Gemini API: {str(e)}"
            print(error_message)
            return error_message

# Factory function to get the appropriate AI provider
def get_ai_provider(provider_name="auto"):
    """
    Get an AI provider based on the provider name.
    
    Args:
        provider_name: The name of the provider to use ('openai', 'google', or 'auto')
        
    Returns:
        An instance of an AIProvider
    """
    # Normalize the provider name
    provider_name = provider_name.lower()
    
    # Print the requested provider
    print(f"Requested AI provider: {provider_name}")
    
    # If explicitly requesting a specific provider, try to use it first
    if provider_name == "openai":
        if OPENAI_AVAILABLE:
            print("Using OpenAI API as explicitly requested")
            return OpenAIProvider()
        else:
            print("OpenAI API requested but not available, falling back")
    
    elif provider_name == "google":
        if GOOGLE_AVAILABLE:
            print("Using Google Gemini API as explicitly requested")
            return GoogleProvider()
        else:
            print("Google Gemini API requested but not available, falling back")
    
    # If using auto or the explicitly requested provider is not available,
    # use the default provider from .env
    default_provider = DEFAULT_AI_PROVIDER.lower()
    
    if default_provider == "openai" and OPENAI_AVAILABLE:
        print("Using OpenAI API from DEFAULT_AI_PROVIDER setting")
        return OpenAIProvider()
    
    elif default_provider == "google" and GOOGLE_AVAILABLE:
        print("Using Google Gemini API from DEFAULT_AI_PROVIDER setting")
        return GoogleProvider()
    
    # If default provider is not available or is set to auto,
    # fall back to available providers
    if OPENAI_AVAILABLE:
        print("Using OpenAI API as fallback")
        return OpenAIProvider()
    
    elif GOOGLE_AVAILABLE:
        print("Using Google Gemini API as fallback")
        return GoogleProvider()
    
    # No providers available
    print("No AI providers available")
    return OpenAIProvider()  # Will return unavailable message 
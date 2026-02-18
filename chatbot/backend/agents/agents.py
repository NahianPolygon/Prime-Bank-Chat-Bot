"""CrewAI Agent definitions for bank chatbot."""

from crewai import Agent, LLM
from tools.search_tools import SearchTools
from tools.eligibility_tools import EligibilityTools
from tools.comparison_tools import ComparisonTools


def get_ollama_llm():
    """Get shared Ollama LLM instance - Local Qwen3 1.7B ONLY via CrewAI LLM wrapper."""
    return LLM(
        model="ollama/qwen3:1.7b",
        base_url="http://ollama:11434",
        temperature=0.3,
    )


class BankAgents:
    """Bank chatbot agents using CrewAI."""
    
    def __init__(self):
        """Initialize with shared Ollama LLM."""
        self.llm = get_ollama_llm()
    
    def intent_classifier_agent(self) -> Agent:
        """Agent 1: Classifies user intent and extracts parameters."""
        return Agent(
            role='Intent Classification Specialist',
            goal='Accurately identify user intent and extract key parameters (banking type, product tier, use case)',
            backstory="""You are an expert at understanding customer banking needs.""",
            tools=[SearchTools.list_available_products],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
        )
    
    def product_retriever_agent(self) -> Agent:
        """Agent 2: Retrieves relevant products from knowledge base."""
        return Agent(
            role='Product Retrieval Expert',
            goal='Find the most relevant bank products based on user criteria',
            backstory="""You are a seasoned banking product specialist.""",
            tools=[SearchTools.search_products, SearchTools.get_product_details, SearchTools.list_available_products],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
        )
    
    def eligibility_analyzer_agent(self) -> Agent:
        """Agent 3: Analyzes customer eligibility for products."""
        return Agent(
            role='Eligibility Analyst',
            goal='Determine if customer meets requirements for each product',
            backstory="""You are a compliance expert.""",
            tools=[EligibilityTools.check_employment_eligibility, EligibilityTools.check_credit_requirements, EligibilityTools.check_document_requirements],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
        )
    
    def feature_comparator_agent(self) -> Agent:
        """Agent 4: Compares features of products."""
        return Agent(
            role='Product Comparison Specialist',
            goal='Create detailed comparisons of product features',
            backstory="""You excel at breaking down complex product features.""",
            tools=[ComparisonTools.compare_products, ComparisonTools.create_comparison_table, ComparisonTools.create_pros_cons_table],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
        )
    
    def response_formatter_agent(self) -> Agent:
        """Agent 5: Formats final response with all information."""
        return Agent(
            role='Response Formatter',
            goal='Compile all analysis into clear, actionable customer response',
            backstory="""You are an expert communicator.""",
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
        )

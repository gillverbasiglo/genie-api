# Genie API

## Overview
Genie API is a FastAPI-based service that processes text using AI models from OpenAI, Groq, and Google. It provides personalized travel recommendations based on user preferences and interests.

## Prerequisites
- Python 3.8 or higher
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- [Postgres.app](https://postgresapp.com/) for PostgreSQL database
- API keys for:
  - OpenAI
  - Groq
  - Google AI Studio

## Getting Started

1. Clone the repository
```bash
git clone https://github.com/GenieTheAI/genie-api.git
cd genie-api
```

2. Install PostgreSQL using Postgres.app
   - Download and install [Postgres.app](https://postgresapp.com/)
   - Open Postgres.app and click "Initialize" to create a new server
   - The default port is 5432
   - Create a new database named `genie_db`

3. Set up Python environment and dependencies
```bash
# Create virtual environment and install dependencies
uv fastapi run dev
```

4. Configure environment variables
```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your configuration
# Required variables:
DATABASE_URL=postgresql://localhost:5432/genie_db
OPENAI_API_KEY=your_openai_api_key
GROQ_API_KEY=your_groq_api_key
GOOGLE_API_KEY=your_google_api_key
```

5. Run database migrations
```bash
# Apply database migrations
alembic upgrade head
```

6. Start the development server
```bash
# Run with hot reload
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## API Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Development

### Database Management
- Use Postgres.app's GUI to manage your database
- Default connection details:
  - Host: localhost
  - Port: 5432
  - Database: genie_db
  - Username: your system username
  - Password: (empty by default)

### Running Tests
```bash
pytest
```

### Code Style
This project follows PEP 8 guidelines. Use the following tools:
```bash
# Format code
black .

# Check code style
flake8

# Sort imports
isort .
```

## Deployment
For production deployment:
1. Set appropriate environment variables
2. Use a production-grade PostgreSQL server
3. Configure proper security measures
4. Use a production ASGI server like Gunicorn

## Contributing
1. Create a new branch for your feature
```bash
git checkout -b feature/your-feature-name
```
2. Make your changes
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License
[Your License]
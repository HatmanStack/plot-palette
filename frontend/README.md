# Plot Palette Frontend

Modern React web application for managing synthetic data generation jobs using AWS Bedrock.

## Features

- 🔐 **Authentication** - AWS Cognito integration with email verification
- 📊 **Dashboard** - Real-time job monitoring with auto-refresh
- ⚙️ **Job Management** - Multi-step wizard for creating generation jobs
- 📝 **Template Editor** - YAML-based prompt template creation
- 💰 **Cost Tracking** - Real-time budget monitoring and warnings
- 📥 **Export Management** - Download generated datasets in multiple formats

## Tech Stack

- **Framework:** React 19 + TypeScript
- **Build Tool:** Vite 7
- **Styling:** Tailwind CSS v4
- **Routing:** React Router v7
- **Data Fetching:** TanStack Query (React Query)
- **HTTP Client:** Axios
- **Authentication:** Amazon Cognito Identity JS
- **Hosting:** AWS Amplify

## Development

### Prerequisites

- Node.js 20+
- npm or yarn

### Setup

```bash
# Install dependencies
npm install

# Create environment file
cp .env.example .env.local

# Update environment variables
VITE_API_ENDPOINT=https://your-api.execute-api.us-east-1.amazonaws.com
VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
VITE_COGNITO_CLIENT_ID=XXXXXXXXXXXXXXXXXX
VITE_REGION=us-east-1
```

### Run Development Server

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### Build for Production

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

## Deployment

### AWS Amplify Deployment

The application is configured for deployment to AWS Amplify using CloudFormation.

#### Prerequisites

- AWS CLI configured with appropriate credentials
- API Gateway endpoint from backend deployment
- Cognito User Pool ID and Client ID

#### Deploy

```bash
# Set environment variables
export API_ENDPOINT="https://your-api.execute-api.us-east-1.amazonaws.com"
export USER_POOL_ID="us-east-1_XXXXXXXXX"
export USER_POOL_CLIENT_ID="XXXXXXXXXXXXXXXXXX"

# Deploy using CloudFormation
cd ..
./infrastructure/scripts/deploy-frontend.sh plot-palette-frontend us-east-1
```

## Project Structure

```
frontend/
├── src/
│   ├── components/       # Reusable UI components
│   ├── routes/          # Page components
│   ├── contexts/        # React contexts
│   ├── services/        # API clients
│   ├── hooks/           # Custom hooks
│   ├── App.tsx          # Root component
│   └── main.tsx         # Entry point
├── public/              # Static assets
├── amplify.yml          # Amplify build configuration
└── package.json
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| VITE_API_ENDPOINT | API Gateway base URL | `https://abc.execute-api.us-east-1.amazonaws.com` |
| VITE_COGNITO_USER_POOL_ID | Cognito User Pool ID | `us-east-1_XXXXXXXXX` |
| VITE_COGNITO_CLIENT_ID | Cognito App Client ID | `XXXXXXXXXXXXXXXXXX` |
| VITE_REGION | AWS Region | `us-east-1` |

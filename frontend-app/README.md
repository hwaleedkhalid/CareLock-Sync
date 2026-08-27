# CareLock Sync - Frontend Application

**Professional Healthcare AI Platform Dashboard**

Built with React + TypeScript + Vite + Tailwind CSS

---

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ 
- npm or yarn
- CareLock-Sync backend running on `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

### Access the Application
- **Development**: http://localhost:5173
- **Login**: Use credentials from backend JWT authentication

---

## 📁 Project Structure

```
src/
├── components/       # Reusable UI components
│   ├── StatCard.tsx
│   └── LoadingSpinner.tsx
├── pages/            # Main application pages
│   ├── LoginPage.tsx
│   ├── DashboardPage.tsx
│   └── PatientsPage.tsx
├── layouts/          # Layout components
│   └── DashboardLayout.tsx
├── services/         # API communication
│   └── api.ts
├── context/          # React Context (Auth)
│   └── AuthContext.tsx
├── types/            # TypeScript definitions
│   └── index.ts
├── App.tsx           # Main app component
└── main.tsx          # Entry point
```

---

## 🔐 Authentication

The application uses JWT-based authentication with the following flow:

1. User logs in via `/login`
2. Backend returns JWT token
3. Token stored in `localStorage`
4. Token automatically attached to all API requests
5. Protected routes redirect to login if not authenticated

**Token Contents:**
- `user_id`
- `username`
- `hospital_id` (tenant isolation)
- `email`

---

## 📊 Features Implemented

✅ **Authentication**
- Login page with validation
- JWT token storage
- Automatic token refresh
- Protected routes

✅ **Dashboard**
- Overview statistics (Patients, Encounters, Observations, Medications)
- Stat cards with icons
- Recent activity feed
- Responsive layout

✅ **Patient Management**
- Patient list with search
- Pagination support
- Patient details view
- Filter and sort capabilities

✅ **Multi-Tenant Support**
- Hospital ID displayed in sidebar
- Tenant-aware API calls
- RLS enforcement via backend

✅ **UI Components**
- Professional healthcare theme
- Responsive sidebar navigation
- Loading states
- Error handling
- Tailwind CSS styling

---

## 🎨 Design System

**Colors:**
- Primary Blue: `#2563eb`
- Success Green: `#10b981`
- Warning Orange: `#f59e0b`
- Danger Red: `#ef4444`

**Typography:**
- System font stack
- Clean, professional spacing
- Accessible font sizes

---

## 🔧 Environment Variables

Create a `.env` file:

```env
VITE_API_URL=http://localhost:8000
```

---

## 📡 API Endpoints Used

- `POST /api/v1/auth/login` - Authentication
- `GET /api/v1/stats` - Dashboard statistics
- `GET /api/v1/patients` - Patient list
- `GET /api/v1/patients/{id}` - Patient details
- `GET /api/v1/encounters` - Encounter list
- `GET /health` - Health check

---

## 🚧 Development Roadmap

**Completed:**
- ✅ Authentication system
- ✅ Dashboard with stats
- ✅ Patient management
- ✅ Responsive layout
- ✅ Multi-tenant support

**Next Steps:**
- ⏳ Encounters page
- ⏳ AI Mapping assistant
- ⏳ Data quality dashboard
- ⏳ System monitoring
- ⏳ Tenant administration

---

## 🛠️ Tech Stack

- **Framework**: React 19 + Vite
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **Routing**: React Router v6
- **HTTP Client**: Axios
- **State Management**: React Context API
- **Authentication**: JWT (jwt-decode)

---

## 📝 Notes

- All API calls automatically include Bearer token
- Token expiration handled with redirect to login
- Responsive design works on mobile, tablet, desktop
- Dark mode support (coming soon)

---

## 👥 Team

- Waleed Khalid
- Muhammad Mohsin
- Shahmeer Nadeem

**Supervisor**: Dr. Muhammad Saqib Sohail

---

## 📄 License

Final Year Project - FAST-NUCES Islamabad

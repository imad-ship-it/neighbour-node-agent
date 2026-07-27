import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Listings from './pages/Listings'
import CreateListingForm from './pages/CreateListingForm'
import './App.css'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Listings />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/create" element={<CreateListingForm />} />
      </Routes>
    </Layout>
  )
}

export default App

import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Listings from './pages/Listings'
import Match from './pages/Match'
import Bookmarks from './pages/Bookmarks'
import CreateListingForm from './pages/CreateListingForm'
import './App.css'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Listings />} />
        <Route path="/match" element={<Match />} />
        <Route path="/saved" element={<Bookmarks />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/create" element={<CreateListingForm />} />
      </Routes>
    </Layout>
  )
}

export default App

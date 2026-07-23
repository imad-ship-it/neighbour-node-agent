import { useQuery } from '@tanstack/react-query'
import client from '../api/client'

async function fetchListings() {
  const { data } = await client.get('/listings/')
  return data
}

export function useListings() {
  return useQuery({ queryKey: ['listings'], queryFn: fetchListings })
}

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Document, TableData, FigureData } from './api'

export function useDocuments() {
  return useQuery({
    queryKey: ['documents'],
    queryFn: api.getDocuments,
  })
}

export function useDocument(id: string) {
  return useQuery({
    queryKey: ['document', id],
    queryFn: () => api.getDocument(id),
    enabled: !!id,
  })
}

export function useTables(documentId: string) {
  return useQuery({
    queryKey: ['tables', documentId],
    queryFn: () => api.getTables(documentId),
    enabled: !!documentId,
  })
}

export function useFigures(documentId: string) {
  return useQuery({
    queryKey: ['figures', documentId],
    queryFn: () => api.getFigures(documentId),
    enabled: !!documentId,
  })
}

export function useExtractText() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (documentId: string) => api.extractText(documentId),
    onSuccess: (_, documentId) => {
      queryClient.invalidateQueries({ queryKey: ['document', documentId] })
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}

export function useIndexDocument() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (documentId: string) => api.indexDocument(documentId),
    onSuccess: (_, documentId) => {
      queryClient.invalidateQueries({ queryKey: ['document', documentId] })
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}

export function useExtractVisuals() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (documentId: string) => api.extractVisuals(documentId),
    onSuccess: (_, documentId) => {
      queryClient.invalidateQueries({ queryKey: ['tables', documentId] })
      queryClient.invalidateQueries({ queryKey: ['figures', documentId] })
      queryClient.invalidateQueries({ queryKey: ['document', documentId] })
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}

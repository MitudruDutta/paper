import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UIState {
  selectedPage: number | null
  setSelectedPage: (page: number | null) => void
  
  selectedTable: string | null
  setSelectedTable: (tableId: string | null) => void
  
  selectedFigure: string | null
  setSelectedFigure: (figureId: string | null) => void
  
  backendAvailable: boolean
  setBackendAvailable: (available: boolean) => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      selectedPage: null,
      setSelectedPage: (page) => set({ selectedPage: page }),
      
      selectedTable: null,
      setSelectedTable: (tableId) => set({ selectedTable: tableId }),
      
      selectedFigure: null,
      setSelectedFigure: (figureId) => set({ selectedFigure: figureId }),
      
      backendAvailable: true,
      setBackendAvailable: (available) => set({ backendAvailable: available }),
    }),
    {
      name: 'paper-ui-state',
      partialize: (state) => ({ 
        selectedPage: state.selectedPage,
      }),
    }
  )
)

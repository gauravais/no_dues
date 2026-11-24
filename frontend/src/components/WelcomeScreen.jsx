
import { useEffect, useState } from 'react'
import './WelcomeScreen.css'

const greetings = [
  'नमस्ते',
  'ਸਤ ਸ੍ਰੀ ਅਕਾਲ',
  'खम्मा घणी',
  'வணக்கம்',
  'કેમ છો?',
  'Hello',
]

export default function WelcomeScreen() {
  const [visible, setVisible] = useState(true)
  const [index, setIndex] = useState(0)
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    let current = 0
    let exitTimeout

    const interval = setInterval(() => {
      if (current < greetings.length - 1) {
        current += 1
        setIndex(current)
      } else {
        clearInterval(interval)
        setExiting(true)

        exitTimeout = setTimeout(() => {
          setVisible(false)
        }, 700)
      }
    }, 600)

    return () => {
      clearInterval(interval)
      clearTimeout(exitTimeout)
    }
  }, [])

  if (!visible) return null

  return (
    <div className={`welcome-screen ${exiting ? 'is-exiting' : ''}`}>
      {!exiting && (
        <h1 key={index} className="welcome-greeting">
          {greetings[index]}
        </h1>
      )}
    </div>
  )
}

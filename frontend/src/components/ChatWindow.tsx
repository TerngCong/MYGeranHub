import type { FormEvent } from 'react'
import { useEffect, useRef, useState, useCallback } from 'react'

import type { ChatMessage } from '../types/chat'
import { MessageBubble } from './MessageBubble'

interface ChatWindowProps {
    messages: ChatMessage[]
    onSend: (prompt: string) => Promise<void>
    isSending: boolean
    language?: 'en' | 'ms'
}

export function ChatWindow({ messages, onSend, isSending, language = 'en' }: ChatWindowProps) {
    const [draft, setDraft] = useState('')
    const viewportRef = useRef<HTMLDivElement | null>(null)
    const textareaRef = useRef<HTMLTextAreaElement | null>(null)

    const scrollToBottom = useCallback(() => {
        viewportRef.current?.scrollTo({
            top: viewportRef.current.scrollHeight,
            behavior: 'auto',
        })
    }, [])

    useEffect(() => {
        viewportRef.current?.scrollTo({
            top: viewportRef.current.scrollHeight,
            behavior: 'smooth',
        })
    }, [messages])

    const handleSubmit = async (event: FormEvent) => {
        event.preventDefault()
        if (!draft.trim()) return
        const value = draft
        setDraft('')
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto'
        }
        await onSend(value)
    }

    const welcomeTitle = language === 'en' ? 'Welcome to MYGeranHub!' : 'Selamat Datang ke MYGeranHub!'
    const welcomeSubtitle = language === 'en' ? 'I am your AI Grant Assistant.' : 'Saya adalah Pembantu Geran AI anda.'

    const useMeTitle = language === 'en' ? 'YOU CAN USE ME TO:' : 'ANDA BOLEH GUNAKAN SAYA UNTUK:'
    const useMeItems = language === 'en' ? [
        "Ask general questions about government grants (e.g., 'What is MDEC?', 'How do I register for tax?').",
        "Find a matching grant by telling me your business profile."
    ] : [
        "Tanya soalan umum tentang geran kerajaan (cth: 'Apa itu MDEC?', 'Apa syarat kelayakan umum?').",
        "Cari geran yang sesuai dengan memberitahu profil perniagaan anda."
    ]

    const trySayingTitle = language === 'en' ? 'TRY SAYING:' : 'CUBA KATAKAN:'
    const trySayingPrompts = language === 'en' ? [
        "\"My company is a car workshop in Kedah seeking RM50k for new machines.\"",
        "\"I run a software house in Selangor and need funding for export.\""
    ] : [
        "\"Syarikat saya adalah bengkel kereta di Kedah, perlukan RM50k untuk mesin baharu.\"",
        "\"Saya ada kedai makan di KL, nak cari geran untuk digitalisasi.\""
    ]

    return (
        <div className="chat-window">
            <div className="chat-viewport" ref={viewportRef}>
                {messages.length === 0 ? (
                    <div className="chat-empty">
                        <h3>{welcomeTitle} <span style={{ fontSize: '0.7em', opacity: 0.7, marginLeft: '0.5rem' }}>MY</span></h3>
                        <p>{welcomeSubtitle}</p>

                        <div className="welcome-card">
                            <h4>{useMeTitle}</h4>
                            <ul>
                                {useMeItems.map((item, i) => <li key={i}>{item}</li>)}
                            </ul>
                        </div>

                        <div className="welcome-card">
                            <h4>{trySayingTitle}</h4>
                            <div className="example-prompts">
                                {trySayingPrompts.map((prompt, i) => (
                                    <blockquote key={i} onClick={() => onSend(prompt.replace(/"/g, ''))} style={{ cursor: 'pointer' }}>
                                        {prompt}
                                    </blockquote>
                                ))}
                            </div>
                        </div>

                        <p style={{ marginTop: '1.5rem', fontSize: '0.9rem', opacity: 0.8 }}>
                            {language === 'en' ? 'How can I help you today?' : 'Bagaimana saya boleh bantu anda hari ini?'}
                        </p>
                    </div>
                ) : (
                    messages.map((message) => <MessageBubble key={message.id} message={message} onContentUpdate={scrollToBottom} />)
                )}
                {isSending && (
                    <div className="thinking-bubble">
                        <div className="thinking-dot"></div>
                        <div className="thinking-dot"></div>
                        <div className="thinking-dot"></div>
                    </div>
                )}
            </div>

            <form className="chat-input" onSubmit={handleSubmit}>
                <textarea
                    ref={textareaRef}
                    value={draft}
                    onChange={(event) => {
                        setDraft(event.target.value);
                        event.target.style.height = 'auto';
                        event.target.style.height = `${Math.min(event.target.scrollHeight, 200)}px`;
                    }}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleSubmit(e);
                        }
                    }}
                    placeholder={language === 'en' ? "Ask about eligible grants, requirements..." : "Tanya mengenai geran yang layak, syarat..."}
                    disabled={isSending}
                    rows={1}
                />
                <button type="submit" disabled={isSending || !draft.trim()}>
                    {isSending ? '...' : (language === 'en' ? 'Send' : 'Hantar')}
                </button>
            </form>
        </div>
    )
}

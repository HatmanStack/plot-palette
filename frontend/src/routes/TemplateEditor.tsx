import { useParams } from 'react-router-dom'

export default function TemplateEditor() {
  const { templateId } = useParams()

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">
        {templateId ? `Edit Template: ${templateId}` : 'New Template'}
      </h1>
      <p className="text-gray-600">Template editor - To be implemented in Task 6</p>
    </div>
  )
}

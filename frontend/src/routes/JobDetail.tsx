import { useParams } from 'react-router-dom'

export default function JobDetail() {
  const { jobId } = useParams()

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Job Detail: {jobId}</h1>
      <p className="text-gray-600">Job detail page - To be implemented in Task 5</p>
    </div>
  )
}

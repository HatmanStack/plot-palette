import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserAttribute,
} from 'amazon-cognito-identity-js'

const userPool = new CognitoUserPool({
  UserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || '',
  ClientId: import.meta.env.VITE_COGNITO_CLIENT_ID || '',
})

export async function signUp(email: string, password: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const attributeList = [
      new CognitoUserAttribute({ Name: 'email', Value: email }),
    ]

    userPool.signUp(email, password, attributeList, [], (err) => {
      if (err) reject(err)
      else resolve()
    })
  })
}

export async function signIn(email: string, password: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: userPool })

    const authDetails = new AuthenticationDetails({
      Username: email,
      Password: password,
    })

    user.authenticateUser(authDetails, {
      onSuccess: (session) => {
        const idToken = session.getIdToken().getJwtToken()
        resolve(idToken)
      },
      onFailure: (err) => reject(err),
    })
  })
}

export function getCurrentUser(): CognitoUser | null {
  return userPool.getCurrentUser()
}

export async function getIdToken(): Promise<string | null> {
  const user = getCurrentUser()
  if (!user) return null

  return new Promise((resolve, reject) => {
    user.getSession((err: Error | null, session: { getIdToken: () => { getJwtToken: () => string } } | null) => {
      if (err) reject(err)
      else if (session) resolve(session.getIdToken().getJwtToken())
      else resolve(null)
    })
  })
}

export function signOut(): void {
  const user = getCurrentUser()
  if (user) user.signOut()
}
